"""The ROMs a player plays, made from their own retail ROMs and the patch files the worlds carry.

- `bk_rom`: the fork's Banjo-Kazooie by itself (the build's `hack/bk/build/bk-fork.z64`), from retail Banjo-Kazooie
  and the BK world's `assets/bk-patch.*`. The patch is a bsdiff between the *uncompressed* ROMs: retail decompressed
  as the decomp does it, and the fork's uncompressed build, so it holds only the hack's changes; the result is then
  compressed as the build does it (bkrom.py, rarezip.py).
- `tooie_rom`: our fork's Tooie hack, from retail Banjo-Tooie and the combined world's `assets/tooie.bsdiff4`, as
  the Tooie world's own patch is applied (Archipelago-BanjoTooie/worlds/banjo_tooie/BTClient.py:185-199).
- `dualboot_image`: the 64 MiB image (`roms/bkbt2-normal.z64`), laid out as tools/make_dualboot_image.py lays it
  out: the Tooie hack at 0, BK's payload at 0x2200000, the info block at 0x2210000, BK at 0x3000000, zeros between,
  and the image's own name in the header (since 2026-11-12; the BK ROM's too, both from the descriptions).

Each refuses a result whose sha1 is not the one the patch files name: what the player gets is what was checked.
tools/make_patches.py writes the patch files from a build and checks that these functions give its ROMs back.
"""

import hashlib
from typing import Mapping

from . import bkrom
from .bkrom import WrongRom

__all__ = ["PatchError", "WrongRom", "bk_rom", "tooie_rom", "dualboot_image", "check_tooie_retail",
           "IMAGE_SIZE", "BK_BASE", "PAYLOAD_OFFSET", "INFO_OFFSET"]

# tools/make_dualboot_image.py:92-98
IMAGE_SIZE = 0x4000000
BK_BASE = 0x3000000
PAYLOAD_OFFSET = 0x2200000
INFO_OFFSET = PAYLOAD_OFFSET + 0x10000

# Retail Banjo-Tooie (USA), as the Tooie world's client takes it (BTClient.py:187-195)
TOOIE_RETAIL_MD5 = "40e98faa24ac3ebe1d25cb5e5ddf49e4"


class PatchError(ValueError):
    """The patch did not give the ROM it names: a damaged patch file, or one of another build."""


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _bspatch(old: bytes, patch: bytes) -> bytes:
    import bsdiff4  # an Archipelago dependency (requirements.txt)
    return bsdiff4.patch(old, patch)


def _named(rom: bytes, info: Mapping, what: str) -> bytes:
    """`rom` with the header name the description carries (since 2026-11-12; tools/make_patches.py)."""
    try:
        return bkrom.header_name(rom, info["header_name"])
    except (KeyError, ValueError):
        raise PatchError(f"the {what} patch's description names no ROM name: patch files of another build") from None


def bk_rom(retail_bk: bytes, patch: bytes, info: Mapping) -> bytes:
    """The fork's Banjo-Kazooie, from retail US v1.0 Banjo-Kazooie in any byte order. `patch` and `info` are the BK
    world's assets/bk-patch.bsdiff4 and assets/bk-patch.json."""
    retail = bkrom.check_retail(retail_bk)
    if _sha1(patch) != info["patch_sha1"]:
        raise PatchError("the Banjo-Kazooie patch file is not the one its description names")
    unc = _bspatch(bkrom.decompress(retail), patch)
    if _sha1(unc) != info["uncompressed_sha1"]:
        raise PatchError("the Banjo-Kazooie patch did not give the uncompressed ROM it names")
    rom = _named(bkrom.sram_header(bkrom.compress(unc, bkrom.Layout(info["layout"]))), info, "Banjo-Kazooie")
    if _sha1(rom) != info["rom_sha1"]:
        raise PatchError("the Banjo-Kazooie ROM made does not have the sha1 the patch names")
    return rom


def check_tooie_retail(rom: bytes) -> bytes:
    """Retail Banjo-Tooie (USA) in big-endian order, or WrongRom saying what `rom` is."""
    rom = bkrom.normalise(rom)
    md5 = hashlib.md5(rom).hexdigest()
    if md5 != TOOIE_RETAIL_MD5:
        if rom[0x20:0x34].rstrip(b" \x00").upper().startswith(b"BANJO TOOIE"):
            raise WrongRom(f"this Banjo-Tooie is not the US one, or not unmodified (MD5 {md5})")
        raise WrongRom(f"this is not Banjo-Tooie (USA) (MD5 {md5})")
    return rom


def tooie_rom(retail_tooie: bytes, patch: bytes, info: Mapping) -> bytes:
    """Our fork's Tooie hack, from retail Banjo-Tooie (USA) in any byte order. `patch` and `info` are the combined
    world's assets/tooie.bsdiff4 and the "tooie" part of assets/image-patch.json."""
    retail = check_tooie_retail(retail_tooie)
    if _sha1(patch) != info["patch_sha1"]:
        raise PatchError("the Banjo-Tooie patch file is not the one its description names")
    rom = _bspatch(retail, patch)
    if _sha1(rom) != info["rom_sha1"]:
        raise PatchError("the Banjo-Tooie ROM made does not have the sha1 the patch names")
    return rom


def dualboot_image(bk: bytes, tooie: bytes, payload: bytes, info_block: bytes, info: Mapping) -> bytes:
    """The dual-boot image from the two hacks (`bk_rom`, `tooie_rom`), BK's payload and the info block (the combined
    world's assets/bk-payload.bin and assets/bkbt-info.bin), as tools/make_dualboot_image.py:475-479 assembles it."""
    for name, data in (("payload", payload), ("info block", info_block)):
        if _sha1(data) != info[f"{name.replace(' ', '_')}_sha1"]:
            raise PatchError(f"the image's {name} file is not the one its description names")
    if len(tooie) > PAYLOAD_OFFSET or len(bk) != bkrom.ROM_SIZE or INFO_OFFSET + len(info_block) > BK_BASE:
        raise PatchError("the image's parts do not fit its layout")
    image = bytearray(IMAGE_SIZE)
    image[0:len(tooie)] = tooie
    image[PAYLOAD_OFFSET:PAYLOAD_OFFSET + len(payload)] = payload
    image[INFO_OFFSET:INFO_OFFSET + len(info_block)] = info_block
    image[BK_BASE:BK_BASE + len(bk)] = bk
    image = _named(bytes(image), info, "image")      # the image's own, over the Tooie hack's "RANDO TOOIE"
    if _sha1(image) != info["image_sha1"]:
        raise PatchError("the image made does not have the sha1 the patch names")
    return image
