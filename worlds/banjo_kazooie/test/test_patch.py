"""The patch in the apworld (patch/, assets/, client/rom.py): Rare's compression, the ROM taken apart and put back, the
patch files, and the client's flow. The tests that need the retail ROM look for it in the repository's roms/ (or
BKBT_ROMS) and are skipped without it."""

import asyncio
import hashlib
import json
import os
import pkgutil
import random
import tempfile
import unittest
import zlib
from pathlib import Path

from ..client import rom
from ..patch import bkrom, make, rarezip

ROMS = Path(os.environ.get("BKBT_ROMS") or Path(__file__).resolve().parents[3] / "roms")
RETAIL_BK = ROMS / "Banjo-Kazooie (USA).z64"


def asset(name: str) -> bytes:
    return pkgutil.get_data("worlds.banjo_kazooie", f"assets/{name}")


def inflate(stream: bytes) -> bytes:
    return zlib.decompressobj(-15).decompress(stream)


class TestRarezip(unittest.TestCase):
    def test_the_decomps_vector(self):
        # hack/bk/decomp/tools/bk_rom_compressor/rarezip/rust/src/tests.rs:20
        self.assertEqual(rarezip.deflate(bytes(20)), bytes.fromhex("6360c00400"))
        self.assertEqual(rarezip.bk_zip(bytes(20))[:6], bytes.fromhex("1172") + (20).to_bytes(4, "big"))

    def test_streams_inflate_back(self):
        rng = random.Random(1)
        words = [bytes(rng.randrange(256) for _ in range(rng.randrange(1, 12))) for _ in range(60)]
        cases = [b"", b"\x01", bytes(300), bytes(range(256)) * 3,
                 b"".join(rng.choice(words) for _ in range(30000)),         # repetitive, longer than the window
                 bytes(rng.randrange(256) for _ in range(70000))]           # little to match
        for data in cases:
            with self.subTest(size=len(data)):
                self.assertEqual(inflate(rarezip.deflate(data)), data)
                self.assertEqual(rarezip.bk_unzip(rarezip.bk_zip(data)), data)

    def test_unzip_refuses_what_is_not_a_stream(self):
        with self.assertRaises(ValueError):
            rarezip.bk_unzip(b"\x00\x00" + bytes(10))


class TestRom(unittest.TestCase):
    def fake(self) -> bytes:
        return b"\x80\x37\x12\x40" + bytes(range(4, 64))

    def test_byte_orders(self):
        z64 = self.fake()
        v64 = bytes(b for i in range(0, len(z64), 2) for b in (z64[i + 1], z64[i]))
        n64 = bytes(b for i in range(0, len(z64), 4) for b in reversed(z64[i:i + 4]))
        for name, data in (("z64", z64), ("v64", v64), ("n64", n64)):
            with self.subTest(name):
                self.assertEqual(bkrom.normalise(data), z64)

    def test_refusals_say_what_the_rom_is(self):
        with self.assertRaisesRegex(bkrom.WrongRom, "not an N64 ROM"):
            bkrom.check_retail(b"PK\x03\x04" + bytes(60))
        with self.assertRaisesRegex(bkrom.WrongRom, "not the US Banjo-Kazooie version 1.0"):
            bkrom.check_retail(self.fake())
        with self.assertRaisesRegex(bkrom.WrongRom, "not Banjo-Tooie"):
            make.check_tooie_retail(self.fake())

    def test_crc(self):
        # src/comp/main.rs:120-127, by hand: a = 1, b = 0xFFFFFFFF ^ (1 << 1); then a = 3, b ^= 2 << 3
        self.assertEqual(bkrom.bk_crc(b"\x01\x02"), (3, 0xFFFFFFFF ^ 2 ^ 16))

    def test_sram_header(self):
        out = bkrom.sram_header(bytes(range(64)) + bytes(16))
        self.assertEqual(out[0x3C:0x3E], b"ED")
        self.assertEqual(out[0x3F], 0x30)
        self.assertEqual(out[0x34:0x38], bytes(4))
        self.assertEqual(out[:0x34], bytes(range(0x34)))


class TestHeaderName(unittest.TestCase):
    def test_written_padded_and_alone(self):
        out = bkrom.header_name(bytes(64), "BK & Tooie AP")
        self.assertEqual(out[0x20:0x34], b"BK & Tooie AP       ")
        self.assertEqual(out[:0x20] + out[0x34:], bytes(44))

    def test_refused(self):
        for bad in ("", "x" * 21, "Banjo-Kazoo\u00efe", "a\tb", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                bkrom.header_name(bytes(64), bad)

    def test_a_description_without_one_is_refused(self):
        with self.assertRaises(make.PatchError):
            make._named(bytes(64), {}, "Banjo-Kazooie")


class TestPatchFiles(unittest.TestCase):
    def test_the_rom_is_named_ap(self):
        """The BK ROM the client makes says it is AP (the owner's decision of 2026-11-12; tools/rom_name.py)."""
        self.assertEqual(json.loads(asset("bk-patch.json"))["header_name"], "Banjo-Kazooie AP")

    def test_description_names_the_patch(self):
        info = json.loads(asset("bk-patch.json"))
        self.assertEqual(info["format"], 1)
        self.assertEqual(hashlib.sha1(asset("bk-patch.bsdiff4")).hexdigest(), info["patch_sha1"])
        self.assertEqual(info["retail_md5"], bkrom.RETAIL_MD5)
        layout = bkrom.Layout(info["layout"])
        self.assertEqual(set(layout.overlays), set(bkrom.OVERLAYS))
        self.assertEqual(set(layout.slots), set(bkrom.CRC_SLOTS))
        self.assertEqual(layout.crc_rom_start, layout.boot[1])

    def test_patch_holds_only_our_changes(self):
        # a diff of the uncompressed ROMs: 77 KB on 2026-11-09, where a diff of the compressed ones is 795 KB
        self.assertLess(len(asset("bk-patch.bsdiff4")), 300_000)


@unittest.skipUnless(RETAIL_BK.is_file(), f"no retail Banjo-Kazooie at {RETAIL_BK}")
class TestFromTheRetailRom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retail = bkrom.check_retail(RETAIL_BK.read_bytes())

    def test_retails_streams_compress_as_rare_did(self):
        offsets = bkrom.RETAIL_STREAMS
        for i in range(len(offsets) - 1):
            piece = self.retail[offsets[i]:offsets[i + 1]]
            with self.subTest(stream=i):
                mine = rarezip.bk_zip(rarezip.bk_unzip(piece))
                self.assertEqual(piece[:len(mine)], mine)
                self.assertFalse(piece[len(mine):].strip(b"\x00"), "only padding after the stream")

    def test_the_patch_gives_the_builds_rom(self):
        info = json.loads(asset("bk-patch.json"))
        made = make.bk_rom(RETAIL_BK.read_bytes(), asset("bk-patch.bsdiff4"), info)
        self.assertEqual(hashlib.sha1(made).hexdigest(), info["rom_sha1"])
        self.assertEqual(len(made), 0x1000000)
        self.assertEqual(made[0x3C:0x3E], b"ED")


class FakeSettings(dict):
    def __getattr__(self, key):
        return self.get(key, "")

    def __setattr__(self, key, value):
        self[key] = value


class TestClientFlow(unittest.TestCase):
    """client/rom.py's ensure_rom with a small target of its own: no retail ROM needed."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="bk-patch-test-")
        self.retail = os.path.join(self.folder, "retail.z64")
        with open(self.retail, "wb") as handle:
            handle.write(b"RETAIL")
        self.made = []

        def check(data: bytes) -> bytes:
            if data != b"RETAIL":
                raise make.WrongRom("this is not the retail one")
            return data

        def build(roms):
            self.made.append(dict(roms))
            return b"MADE:" + roms["rom_path"]

        self.target = rom.Target("Test", "Test AP 1.z64", hashlib.sha1(b"MADE:RETAIL").hexdigest(),
                                 (rom.Source("rom_path", "Test (USA)", check),), build, 1)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.folder, ignore_errors=True)

    def ensure(self, settings, ask=lambda title: None):
        return asyncio.run(rom.ensure_rom(settings, self.target, ask=ask))

    def test_makes_it_once(self):
        settings = FakeSettings(patch_path=self.folder, rom_path=self.retail)
        path = self.ensure(settings)
        self.assertEqual(Path(path).read_bytes(), b"MADE:RETAIL")
        self.assertEqual(self.ensure(settings), path)
        self.assertEqual(len(self.made), 1, "a current ROM is not made again")
        self.assertFalse(os.path.exists(path + ".part"))

    def test_asks_for_a_rom_it_does_not_know_and_keeps_it(self):
        settings = FakeSettings(patch_path=self.folder)
        asked = []
        path = self.ensure(settings, ask=lambda title: asked.append(title) or self.retail)
        self.assertTrue(path)
        self.assertEqual(asked, ["Open your Test (USA) ROM"])
        self.assertEqual(settings.rom_path, self.retail)

    def test_a_wrong_rom_is_refused_and_forgotten(self):
        wrong = os.path.join(self.folder, "wrong.z64")
        with open(wrong, "wb") as handle:
            handle.write(b"OTHER")
        settings = FakeSettings(patch_path=self.folder, rom_path=wrong)
        with self.assertLogs("Client", level="ERROR") as logs:
            self.assertIsNone(self.ensure(settings))
        self.assertIn("wrong.z64: this is not the retail one", logs.output[0])
        self.assertEqual(settings.rom_path, "")
        self.assertEqual(self.made, [])

    def test_an_old_rom_is_made_again(self):
        settings = FakeSettings(patch_path=self.folder, rom_path=self.retail)
        Path(self.folder, "Test AP 1.z64").write_bytes(b"an older build")
        self.ensure(settings)
        self.assertEqual(len(self.made), 1)

    def test_other_worlds_settings_are_tried_first(self):
        other = FakeSettings(rom_path=self.retail)
        target = rom.Target(self.target.title, self.target.file_name, self.target.sha1,
                            (rom.Source("bk_rom_path", "Test (USA)", self.target.sources[0].check,
                                        ((other, "rom_path"),)),),
                            lambda roms: b"MADE:" + roms["bk_rom_path"], 1)
        settings = FakeSettings(patch_path=self.folder)
        path = asyncio.run(rom.ensure_rom(settings, target, ask=lambda title: self.fail("asked")))
        self.assertTrue(path)
        self.assertEqual(settings.bk_rom_path, self.retail)
