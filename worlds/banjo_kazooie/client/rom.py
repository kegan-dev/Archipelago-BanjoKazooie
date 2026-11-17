"""The ROM a client plays, made from the player's own retail ROMs with the world's patch (patch/make.py).

As the Tooie client makes its own (Archipelago-BanjoTooie/worlds/banjo_tooie/BTClient.py:185-270): on start, and on
/patch, the client looks for "<game> AP <version>.z64" in the patch folder; if it is missing, or not the ROM this
version makes (its sha1), it asks once for each retail ROM it needs (kept in host.yaml), makes the ROM and writes it
there. The ROM holds no seed's data, so one serves every seed. With /autostart the client then starts the
emulator with it.

The Banjo-Kazooie client makes the fork's Banjo-Kazooie (`bk_target`), the Banjo-Kazooie & Tooie client the dual-boot
image (its `image_target`, worlds/banjo_kazooie_tooie/BKBTClient.py).
"""

import asyncio
import hashlib
import json
import os
import pkgutil
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import Utils
from CommonClient import ClientCommandProcessor, logger

from ..patch import make

ROM_TYPES = (("N64 ROMs", (".z64", ".n64", ".v64")), ("All Files", "*"))

_program: Optional[subprocess.Popen] = None     # the emulator /autostart started


@dataclass(frozen=True)
class Source:
    """A retail ROM a patch needs: the setting that holds its path, and other worlds' settings to try first when
    that is blank (attribute names of `fallbacks`' settings groups)."""
    key: str
    label: str
    check: Callable[[bytes], bytes]
    fallbacks: Tuple[Tuple[Any, str], ...] = ()


@dataclass(frozen=True)
class Target:
    """The ROM a client plays: its file name, its sha1, the retail ROMs it is made from, and how."""
    title: str
    file_name: str
    sha1: str
    sources: Sequence[Source]
    make: Callable[[Dict[str, bytes]], bytes]
    seconds: int        # about how long making it takes, for the log


def world_asset(package: str, name: str) -> bytes:
    """A file of a world's assets/ (a folder or a zipped .apworld)."""
    data = pkgutil.get_data(package, f"assets/{name}")
    if data is None:
        raise FileNotFoundError(f"{package} has no assets/{name}")
    return data


# The BK world's package, whose assets/ hold its patch: worlds.banjo_kazooie, or worlds.banjo_kazooie_tooie.bk where the
# combined world carries it (worlds/banjo_kazooie_tooie/carried.py); this module is <package>.client.rom.
BK_PACKAGE = __name__.rsplit(".", 2)[0]


def bk_patch_files() -> Tuple[bytes, Dict]:
    return (world_asset(BK_PACKAGE, "bk-patch.bsdiff4"),
            json.loads(world_asset(BK_PACKAGE, "bk-patch.json")))


def bk_target(version: str) -> Target:
    """The fork's Banjo-Kazooie by itself, for a Banjo-Kazooie slot."""
    patch, info = bk_patch_files()
    source = Source("rom_path", "Banjo-Kazooie (USA)", make.bkrom.check_retail)
    return Target("Banjo-Kazooie", f"Banjo-Kazooie AP {version}.z64", info["rom_sha1"], (source,),
                  lambda roms: make.bk_rom(roms["rom_path"], patch, info), 10)


def _setting(group: Any, key: str) -> str:
    try:
        value = group.get(key, "") if hasattr(group, "get") else getattr(group, key, "")
    except Exception:
        value = ""
    return str(value or "")


def output_path(settings: Any, file_name: str) -> Optional[str]:
    """Where the ROM goes, as Tooie's client decides it (BTClient.py:209-218): the patch folder if set and writable,
    else Archipelago's user folder, else its cache."""
    folder = _setting(settings, "patch_path")
    if folder and os.path.isdir(folder) and os.access(folder, os.W_OK):
        return os.path.join(folder, file_name)
    if os.access(Utils.user_path(), os.W_OK):
        return Utils.user_path(file_name)
    if os.access(Utils.cache_path(), os.W_OK):
        return Utils.cache_path(file_name)
    return None


def file_sha1(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _save(settings: Any, key: str, value: str) -> None:
    setattr(settings, key, value)
    settings._changed = True


def _retail(settings: Any, source: Source, ask: Callable[[str], Optional[str]]) -> Optional[bytes]:
    """The retail ROM for `source`, checked: from its setting, else another world's, else the player picks it.
    None (and a log line) when there is none or it is not the right ROM."""
    path = _setting(settings, source.key)
    if not path or not os.path.isfile(path):
        path = next((_setting(group, key) for group, key in source.fallbacks
                     if os.path.isfile(_setting(group, key))), "")
    if not path or not os.path.isfile(path):
        path = ask(f"Open your {source.label} ROM") or ""
    if not path:
        logger.error(f"No {source.label} ROM chosen: use /patch to try again.")
        return None
    try:
        with open(path, "rb") as handle:
            rom = source.check(handle.read())
    except make.WrongRom as exc:
        logger.error(f"{os.path.basename(path)}: {exc}. Use /patch to choose another.")
        if _setting(settings, source.key) == path:
            _save(settings, source.key, "")
        return None
    except OSError as exc:
        logger.error(f"Could not read {path}: {exc}. Use /patch to try again.")
        return None
    if _setting(settings, source.key) != path:
        _save(settings, source.key, path)
    return rom


def _ask(title: str) -> Optional[str]:
    return Utils.open_filename(title, ROM_TYPES)


async def ensure_rom(settings: Any, target: Target, show_path: bool = True,
                     ask: Callable[[str], Optional[str]] = _ask) -> Optional[str]:
    """The path of `target`'s ROM, made first if it is not there or not current; None (with the reason logged) when
    it cannot be made."""
    path = output_path(settings, target.file_name)
    if path is None:
        logger.error("Found no folder to write the ROM to: set one with /patch_path, then /patch.")
        return None
    loop = asyncio.get_running_loop()
    if await loop.run_in_executor(None, file_sha1, path) == target.sha1:
        if show_path:
            logger.info(f"The {target.title} ROM is here: {path}")
        return path
    roms = {}
    for source in target.sources:
        rom = _retail(settings, source, ask)
        if rom is None:
            return None
        roms[source.key] = rom
    logger.info(f"Making the {target.title} ROM from your ROMs (about {target.seconds} seconds)...")
    try:
        data = await loop.run_in_executor(None, target.make, roms)
    except (make.PatchError, make.WrongRom) as exc:
        logger.error(f"Could not make the {target.title} ROM: {exc}. Reinstall the apworld, then /patch.")
        return None
    temporary = path + ".part"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    except OSError as exc:
        logger.error(f"Could not write {path}: {exc}. Set another folder with /patch_path, then /patch.")
        return None
    if _setting(settings, "patch_path") != os.path.dirname(path):
        _save(settings, "patch_path", os.path.dirname(path))
    logger.info(f"Made the {target.title} ROM: {path}  (sha1 {target.sha1[:12]}). Open it in your emulator.")
    return path


def start_program(settings: Any, rom_path: str) -> None:
    """Start the emulator /autostart set, with the ROM, unless it is still running (BTClient.py:247-270)."""
    global _program
    program = _setting(settings, "program_path")
    if not program or not os.path.isfile(program) or (_program is not None and _program.poll() is None):
        return
    logger.info(f"Starting {program}")
    args = [*shlex.split(program)]
    extra = _setting(settings, "program_args")
    if extra:
        args.append(extra)
    args.append(rom_path)
    _program = subprocess.Popen(args, cwd=Utils.local_path("."), stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def patch_and_run(settings: Any, target: Target, show_path: bool = True) -> Optional[str]:
    """Make the ROM if needed, then start the emulator if /autostart set one."""
    try:
        path = await ensure_rom(settings, target, show_path)
    except Exception as exc:    # the client keeps running; the player can try again
        logger.exception(f"Making the {target.title} ROM failed: {exc}")
        return None
    if path:
        start_program(settings, path)
    return path


class RomCommands(ClientCommandProcessor):
    """The client commands for the ROM, for a client whose context has `rom_settings` (the world's settings group)
    and `rom_target()`. Each client's processor adds its own command for each retail ROM's path."""

    def _cmd_patch(self) -> bool:
        """Make the ROM from your retail ROMs again if it is missing or out of date, and say where it is."""
        ctx = self.ctx
        Utils.async_start(patch_and_run(ctx.rom_settings, ctx.rom_target(), True), name="patch")
        return True

    def set_rom_path(self, key: str, label: str, path: str) -> bool:
        """For a processor's own /..._rom_path command: set (or unset) where a retail ROM is."""
        if path and not os.path.isfile(path):
            logger.error(f"There is no file {path}.")
            return False
        _save(self.ctx.rom_settings, key, path)
        logger.info(f"The {label} ROM {'is ' + path if path else 'is asked for again at the next /patch'}.")
        return True

    def _cmd_patch_path(self, path: str = "") -> bool:
        """Set (or, with no argument, unset) the folder the ROM is written to."""
        _save(self.ctx.rom_settings, "patch_path", path)
        logger.info(f"patch_path {'set' if path else 'unset'}.")
        return True

    def _cmd_autostart(self) -> bool:
        """Choose a program (your emulator) to start with the ROM; again to stop doing it."""
        ctx = self.ctx
        settings = ctx.rom_settings
        if _setting(settings, "program_path") and os.path.isfile(_setting(settings, "program_path")):
            _save(settings, "program_path", "")
            logger.info("Autostart disabled.")
            return True
        program = Utils.open_filename("Select the program to start with the ROM", (("All Files", "*"),))
        if not program:
            logger.error("No program chosen.")
            return False
        _save(settings, "program_path", program)
        logger.info(f"Autostart configured for: {program}")
        Utils.async_start(patch_and_run(settings, ctx.rom_target(), False), name="patch")
        return True
