"""Banjo-Kazooie's ROM taken apart and put back together, in pure Python, as the decomp's tools do it.

`decompress` is `bk_rom_decompress` and `compress` is `bk_rom_compress` (hack/bk/decomp/tools/bk_rom_compressor/
src/decomp/main.rs and src/comp/main.rs, cic.rs; paths below are in that directory). The patch in the apworld goes
between them: the player's retail ROM decompressed, the fork's uncompressed build made from it by a bsdiff, and that
compressed again to exactly the build's ROM (patch/make.py). The compression is rarezip's (patch/rarezip.py).

What `compress` needs from the build's ELF (each overlay's ROM range, text length and data address, the boot
segment's range, the CRC block's place, the CRC slots in the data) is a `Layout`, which tools/make_patches.py
writes from the build's linker map into the patch files.
"""

import hashlib
from typing import Dict, List, Optional, Sequence, Tuple

from . import rarezip

__all__ = ["WrongRom", "RETAIL_MD5", "normalise", "check_retail", "decompress", "compress", "bk_crc",
           "cic_6103_checksum", "sram_header", "OVERLAYS"]

ROM_SIZE = 0x1000000

# src/decomp/main.rs:28-37: the four versions the decomp knows, by the MD5 of the big-endian ROM
RETAIL_MD5 = "b29599651a13f681c9923d69354bf4a3"     # NTSC-U v1.0, the one the hack is built on
OTHER_VERSIONS = {
    "06a43bacf5c0687f596df9b018ca6d7f": "the European (PAL) Banjo-Kazooie",
    "3d3855a86fd5a1b4d30beb0f5a4a85af": "the Japanese Banjo-Kazooie",
    "b11f476d4bc8e039355241e871dc08cf": "the US Banjo-Kazooie version 1.1",
}

# src/decomp/main.rs:89-107: retail US v1.0's compressed code and data, each overlay's code then data
RETAIL_STREAMS = (
    0xF19250, 0xF19250 + 0x1D09B,   # core1
    0xF37F90, 0xF37F90 + 0x64B50,   # core2
    0xFA3FD0, 0xFA3FD0 + 0x1DC6,    # whale (CC)
    0xFA5F50, 0xFA5F50 + 0x2D96,    # haunted (MMM)
    0xFA9150, 0xFA9150 + 0x512E,    # desert (GV)
    0xFAE860, 0xFAE860 + 0x328B,    # beach (TTC)
    0xFB24A0, 0xFB24A0 + 0x1E39,    # jungle (MM)
    0xFB44E0, 0xFB44E0 + 0x5130,    # swamp (BGS)
    0xFB9A30, 0xFB9A30 + 0x4BB2,    # ship (RBB)
    0xFBEBE0, 0xFBEBE0 + 0x540F,    # snow (FP)
    0xFC4810, 0xFC4810 + 0x23FF,    # training (SM)
    0xFC6F20, 0xFC6F20 + 0x1BDC,    # intro (cutscenes)
    0xFC9150, 0xFC9150 + 0x6548,    # witch (lair)
    0xFD0420, 0xFD0420 + 0x5640,    # battle (fight)
    0xFD6190, 0xFD6190 + 0x416F,    # tree (CCW)
    0xFDAA10, 0xFDAA10 + 0xE,       # coshow (emptyLvl)
    0xFDAA30,
)

# src/comp/main.rs:158: the overlays in the ELF's order (the uncompressed ROM's); the compressed ROM has MMM before
# GV, as retail (:281-282)
OVERLAYS = ("core1", "core2", "CC", "GV", "MMM", "TTC", "MM", "BGS", "RBB", "FP", "SM", "cutscenes", "lair",
            "fight", "CCW", "emptyLvl")
# src/comp/main.rs:178-245: the levels whose data holds their code's CRC, and the three slots of each
LEVEL_CRC_SLOTS = (
    ("SM", ("D_8038AAE0", "D_8038AAE4", "D_8038AAE8")),
    ("MM", ("D_803899C0", "D_803899C4", "D_803899C8")),
    ("TTC", ("D_8038C750", "D_8038C754", "D_8038C758")),
    ("BGS", ("D_80390B20", "D_80390B24", "D_80390B28")),
    ("CC", ("D_80389BE0", "D_80389BE4", "D_80389BE8")),
    ("GV", ("D_80390F30", "D_80390F34", "D_80390F38")),
    ("MMM", ("D_8038C300", "D_8038C304", "D_8038C308")),
)
CORE2_CODE_CRC = "D_803727F4"       # core2's data: core2's code CRC, second word (:258)
CORE1_CORE2_DATA_CRC = "D_80276574"  # core1's data: core2's data CRC, second word (:262)
CORE1_SM_DATA_CRC = "D_80275650"     # core1's data: SM's data CRC with its slots filled, second word (:263)
CRC_SLOTS = tuple(name for _level, names in LEVEL_CRC_SLOTS for name in names) + (
    CORE2_CODE_CRC, CORE1_CORE2_DATA_CRC, CORE1_SM_DATA_CRC)


class WrongRom(ValueError):
    """A ROM that is not the one the patch is made for; the message says what it is, for the player."""


def normalise(rom: bytes) -> bytes:
    """The ROM in big-endian (.z64) byte order, from any of the three (src/decomp/main.rs:53-61)."""
    head = bytes(rom[:4])
    if head == b"\x80\x37\x12\x40":
        return bytes(rom)
    if head == b"\x40\x12\x37\x80":         # little-endian (.n64)
        out = bytearray(len(rom))
        for k in range(4):
            out[k::4] = rom[3 - k::4]
        return bytes(out)
    if head == b"\x37\x80\x40\x12":         # byte-swapped (.v64)
        out = bytearray(len(rom))
        out[0::2] = rom[1::2]
        out[1::2] = rom[0::2]
        return bytes(out)
    raise WrongRom("this is not an N64 ROM")


def check_retail(rom: bytes) -> bytes:
    """The retail US v1.0 Banjo-Kazooie in big-endian order, or WrongRom saying what `rom` is."""
    rom = normalise(rom)
    md5 = hashlib.md5(rom).hexdigest()
    if md5 == RETAIL_MD5:
        return rom
    if md5 in OTHER_VERSIONS:
        raise WrongRom(f"this is {OTHER_VERSIONS[md5]}; the patch needs the US Banjo-Kazooie, version 1.0")
    raise WrongRom(f"this is not the US Banjo-Kazooie version 1.0 (MD5 {md5}): another game, or a modified or bad dump")


def decompress(retail: bytes) -> bytes:
    """The uncompressed ROM the decomp builds against, from retail US v1.0 in big-endian order
    (src/decomp/main.rs:130-155): the ROM up to core1, then every overlay's code and data inflated, in the ELF's
    order, without padding."""
    pieces = [rarezip.bk_unzip(retail[RETAIL_STREAMS[i]:RETAIL_STREAMS[i + 1]])
              for i in range(len(RETAIL_STREAMS) - 1)]
    pieces[6], pieces[8] = pieces[8], pieces[6]     # MMM and GV back in the ELF's order
    pieces[7], pieces[9] = pieces[9], pieces[7]
    return bytes(retail[:RETAIL_STREAMS[0]]) + b"".join(pieces)


def bk_crc(data: bytes) -> Tuple[int, int]:
    """Banjo-Kazooie's two-word checksum (src/comp/main.rs:120-127): the mask is 0x17, and the shift uses the sum
    after the byte."""
    a, b = 0, 0xFFFFFFFF
    for byte in data:
        a = (a + byte) & 0xFFFFFFFF
        b ^= byte << (a & 0x17)
    return a, b & 0xFFFFFFFF


def _crc32(data: bytes) -> int:
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def cic_6103_checksum(rom: bytes) -> bytes:
    """The header checksum (0x10..0x17) of a CIC-6103 ROM over 0x1000..0x101000 (src/comp/cic.rs:65-88)."""
    if _crc32(rom[0x40:0x1000]) != 0x0B050EE0:
        raise ValueError("the boot code is not the CIC-6103's")
    t1 = t2 = t3 = t4 = t5 = t6 = 0xA3886759
    mask = 0xFFFFFFFF
    section = rom[0x1000:0x101000]
    for i in range(0, 0x100000, 4):
        d = int.from_bytes(section[i:i + 4], "big")
        if (t6 + d) & mask < t6:
            t4 = (t4 + 1) & mask
        t6 = (t6 + d) & mask
        t3 ^= d
        s = d & 0x1F
        r = ((d << s) | (d >> (32 - s))) & mask if s else d
        t5 = (t5 + r) & mask
        t2 ^= r if t2 > d else (t6 ^ d)
        t1 = (t1 + (d ^ t5)) & mask
    return (((t6 ^ t4) + t3) & mask).to_bytes(4, "big") + (((t5 ^ t2) + t1) & mask).to_bytes(4, "big")


def sram_header(rom: bytes) -> bytes:
    """The ROM with the header the export has (hack/build_bk_rom.sh, tools/ed64romconfig.py -w sram256k): 'ED' at
    0x3C, the save type SRAM 256k at 0x3F, plain controllers at 0x34..0x37. Outside the checksum's range."""
    out = bytearray(rom)
    out[0x3C:0x3E] = b"ED"
    out[0x3F] = 0x30
    out[0x34:0x38] = bytes(4)
    return bytes(out)


NAME_AT, NAME_SIZE = 0x20, 20      # the header's name, which emulators show (tools/rom_name.py)


def header_name(rom: bytes, name: str) -> bytes:
    """The ROM with `name` in its header, as the build writes it (tools/rom_name.py: the export's "Banjo-Kazooie AP",
    the image's "BK & Tooie AP"): 1..20 printable ASCII characters, padded with spaces. Outside the checksum's
    range."""
    if not isinstance(name, str) or not 0 < len(name) <= NAME_SIZE or not all(0x20 <= ord(c) < 0x7F for c in name):
        raise ValueError(f"a ROM name is 1..{NAME_SIZE} printable ASCII characters: {name!r}")
    return rom[:NAME_AT] + name.encode("ascii").ljust(NAME_SIZE, b" ") + rom[NAME_AT + NAME_SIZE:]


class Layout:
    """What `compress` needs from the build's ELF, by name as src/comp/main.rs looks it up:
    `boot`: boot_bk_boot_ROM_START and _ROM_END; `crc_rom_start`: crc_ROM_START; `overlays`: for each name of
    OVERLAYS, its ROM_START, ROM_END, text length (TEXT_END - TEXT_START; core1's to core1_DATA_START_OFFSET) and data
    address (DATA_START; core1's DATA_START_OFFSET); `slots`: each CRC slot's address (CRC_SLOTS; a missing one is
    skipped, as the tool does with a warning)."""

    def __init__(self, data: Dict):
        self.boot = tuple(data["boot"])
        self.crc_rom_start = data["crc_rom_start"]
        self.overlays = {name: dict(info) for name, info in data["overlays"].items()}
        self.slots = dict(data["slots"])
        missing = [name for name in OVERLAYS if name not in self.overlays]
        if missing:
            raise ValueError(f"the layout has no {', '.join(missing)}")

    def to_json(self) -> Dict:
        return {"boot": list(self.boot), "crc_rom_start": self.crc_rom_start, "overlays": self.overlays,
                "slots": self.slots}


def compress(unc: bytes, layout: Layout) -> bytes:
    """The compressed 16 MiB ROM from the uncompressed one, as src/comp/main.rs:129-342 makes it."""
    codes: List[bytes] = []
    datas: List[bytearray] = []
    for name in OVERLAYS:
        info = layout.overlays[name]
        start, end, text_len = info["rom_start"], info["rom_end"], info["text_len"]
        codes.append(bytes(unc[start:start + text_len]))
        datas.append(bytearray(unc[start + text_len:end]))
    code_crcs = [bk_crc(code) for code in codes]
    index = {name: i for i, name in enumerate(OVERLAYS)}

    def put(name: str, symbol: str, value: int) -> None:
        address = layout.slots.get(symbol)
        if address is None:
            return      # the tool warns and goes on (:183-186)
        at = address - layout.overlays[name]["data_start"]
        datas[index[name]][at:at + 4] = value.to_bytes(4, "big")

    sm_full = (0, 0)
    for name, (first, second, third) in LEVEL_CRC_SLOTS:
        i = index[name]
        put(name, first, code_crcs[i][0])
        put(name, second, code_crcs[i][1])
        put(name, third, 0)
        put(name, third, bk_crc(datas[i])[0])
        if name == "SM":
            sm_full = bk_crc(datas[i])
    put("core2", CORE2_CODE_CRC, code_crcs[index["core2"]][1])
    core2_data = bk_crc(datas[index["core2"]])
    put("core1", CORE1_CORE2_DATA_CRC, core2_data[1])
    put("core1", CORE1_SM_DATA_CRC, sm_full[1])
    core1_data = bk_crc(datas[index["core1"]])
    core1_code = code_crcs[index["core1"]]

    packed = []
    for code, data in zip(codes, datas):
        piece = rarezip.bk_zip(code) + rarezip.bk_zip(bytes(data))
        packed.append(piece + bytes(((len(piece) + 15) & ~15) - len(piece)))
    packed[3], packed[4] = packed[4], packed[3]     # MMM before GV in the ROM

    boot_start, boot_end = layout.boot
    boot = bytes(unc[boot_start:boot_end])
    boot_crc = bk_crc(boot)
    crc_block = b"".join(word.to_bytes(4, "big") for word in (*boot_crc, *core1_code, *core1_data)) + bytes(8)
    overlay_start = layout.overlays["core1"]["rom_start"]
    rom = bytearray(unc[:boot_start])
    rom += boot
    rom += crc_block
    rom += unc[layout.crc_rom_start + 0x20:overlay_start]
    for piece in packed:
        rom += piece
    if len(rom) > ROM_SIZE:
        raise ValueError(f"the compressed ROM is {len(rom)} bytes, more than 16 MiB")
    rom += b"\xFF" * (ROM_SIZE - len(rom))
    rom[0x10:0x18] = cic_6103_checksum(bytes(rom[:0x101000]))
    return bytes(rom)
