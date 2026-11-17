"""The Banjo-Kazooie client: between an Archipelago server and the hack's ROM in an emulator.

It plays Banjo-Kazooie built from the fork (hack/bk/build/bk-fork.z64) or the dual-boot image
(roms/bkbt2-normal.z64), in Project64 or ares (any emulator emu_loader attaches to). On start, and on /patch, it makes
"Banjo-Kazooie AP <version>.z64" from the player's own Banjo-Kazooie ROM with the world's patch if it is not there yet
(client/rom.py), and it
- gives the game every item received, with the slot's seed, skip_intro, notesanity and skip_lair_cutscene (client/hack.py; the items as the game
  takes them, client/ids.py) and the exit map of the slot's world doors (client/ids.py, exits_of), and again after
  every boot;
- sends a check for every location the game publishes, and the goal once Gruntilda is beaten;
- with the slot's death_link and tag_link, sends Banjo's deaths and his D-pad left swaps and gives the game those of
  the other players, and gives it the traps received (client/link.py, the hack's link block);
- waits while Tooie runs in the dual-boot image, and writes again once BK is back.

Start it from the Archipelago Launcher ("Banjo-Kazooie Client"). docs/DEVELOPMENT.md has how to play a seed by hand.
"""

import asyncio
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import Utils
from CommonClient import CommonContext, get_base_parser, gui_enabled, handle_url_arg, logger, server_loop
from NetUtils import ClientStatus

from . import BanjoKazooieWorld
from .Items import all_item_table
from .client import hack, ids, rom
from .client.emu import load as load_emu_loader
from .client.link import LinkDriver, Sent

NAME_OF_ID = {data.bkid: name for name, data in all_item_table.items()}

POLL = 0.2              # seconds between two looks at the game, as Tooie's client (BTClient.py:1360)
ATTACH_RETRY = 2.0      # seconds between two searches for an emulator running BK
RESCAN_AFTER = 60.0     # seconds of no BK at the attached RAM before looking for it elsewhere (a ROM reloaded)
ITEMS_GRACE = 1.0       # seconds after Connected to wait for ReceivedItems before writing without any


class BanjoKazooieCommandProcessor(rom.RomCommands):
    ctx: "BanjoKazooieContext"

    def _cmd_rom_path(self, path: str = "") -> bool:
        """Set (or, with no argument, unset) the file path of your Banjo-Kazooie (USA) ROM, which /patch makes the
        ROM from."""
        return self.set_rom_path("rom_path", "Banjo-Kazooie (USA)", path)

    def _cmd_deathlink(self) -> bool:
        """Turn death link on or off for this session (the slot's setting is the start)."""
        ctx = self.ctx
        Utils.async_start(ctx.update_death_link("DeathLink" not in ctx.tags), name="death link")
        logger.info(f"Death link {'off' if 'DeathLink' in ctx.tags else 'on'}.")
        return True

    def _cmd_taglink(self) -> bool:
        """Turn tag link on or off for this session (the slot's setting is the start)."""
        ctx = self.ctx
        Utils.async_start(ctx.update_tag_link("TagLink" not in ctx.tags), name="tag link")
        logger.info(f"Tag link {'off' if 'TagLink' in ctx.tags else 'on'}.")
        return True

    def _cmd_bk(self) -> bool:
        """Show the emulator, the game's state and what the client gives it."""
        ctx = self.ctx
        last = ctx.link.last
        found = ctx.link.found
        logger.info(f"Emulator: {ctx.emu_status}")
        logger.info(f"Banjo-Kazooie: {last.state}: {last.reason}"
                    + (f" (layout {'.'.join(map(str, found.version))})" if found else ""))
        logger.info(f"Server: {'slot ' + str(ctx.auth) if ctx.slot is not None else 'not connected'}"
                    + (f", seed 0x{ctx.slot_data['seed']:08X}" if isinstance(ctx.slot_data.get('seed'), int) else ""))
        logger.info(f"Gives: {hack.describe(ctx.wanted_items())}")
        doors = ctx.slot_data.get("world_entrances") or {}
        moved = [f"{door} -> {world}" for door, world in doors.items() if door != world]
        logger.info(f"World doors: {', '.join(moved) if moved else 'each to its own world'}")
        logger.info(f"Checks the game shows: {len(last.checks)}; sent this session: {len(ctx.sent)}; "
                    f"goal: {'sent' if ctx.finished_game else 'not yet'}; commits: {ctx.link.commits}")
        logger.info(ctx.link_driver.describe())
        return True


class BanjoKazooieContext(CommonContext):
    game = "Banjo-Kazooie"
    items_handling = 0b111      # every item: from other worlds, from this one and the starting ones
    command_processor = BanjoKazooieCommandProcessor

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)
        self.slot_data: Dict[str, Any] = {}
        self.link = hack.Link()
        self.emu_status = "not attached"
        self.emulator_task: Optional[asyncio.Task] = None
        self.connected_at = 0.0
        self.items_ready = False
        self.sent: Set[int] = set()             # location ids sent since Connected
        self.told: Set[Any] = set()             # what has been logged once
        self.last_state: Optional[str] = None
        self.link_driver = LinkDriver()         # deaths, tags and traps while BK runs (client/link.py)
        self.instance_id = time.time()          # tag link: a tag of our own coming back is not one for us

    @property
    def rom_settings(self) -> Any:
        """This world's settings in host.yaml (its BanjoKazooieSettings), read when first needed."""
        return BanjoKazooieWorld.settings

    def rom_target(self) -> rom.Target:
        return rom.bk_target(BanjoKazooieWorld.world_version.as_simple_string())

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: Dict[str, Any]) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data") or {}
            self.connected_at = time.monotonic()
            self.items_ready = False
            self.sent.clear()
            Utils.async_start(self.update_death_link(bool(self.slot_data.get("death_link"))), name="death link")
            Utils.async_start(self.update_tag_link(bool(self.slot_data.get("tag_link"))), name="tag link")
            seed = self.slot_data.get("seed")
            if not isinstance(seed, int) or not 0 < seed <= 0xFFFFFFFF:
                logger.error("This slot has no seed for the game: it was generated by an older Banjo-Kazooie world. "
                             "Generate it again.")
            layout = tuple(self.slot_data.get("layout") or ())
            if layout and layout > hack.WANT:
                logger.warning(f"This slot was generated for layout {'.'.join(map(str, layout))} of the hack; this "
                               f"client knows {hack.WANT[0]}.{hack.WANT[1]}. Update the Banjo-Kazooie apworld.")
        elif cmd == "ReceivedItems":
            self.items_ready = True
        elif cmd == "Bounced" and "TagLink" in args.get("tags", []) and "TagLink" in self.tags:
            # as the Banjo-Tooie client takes a tag (Archipelago-BanjoTooie/worlds/banjo_tooie/BTClient.py:593-601)
            data = args.get("data") or {}
            if isinstance(data, dict) and data.get("source") != self.instance_id:
                self.link_driver.owe(tags=1)

    def on_deathlink(self, data: Dict[str, Any]) -> None:
        super().on_deathlink(data)
        self.link_driver.owe(deaths=1)

    async def update_tag_link(self, tag_link: bool) -> None:
        """The TagLink tag on or off, told to the server if connected (as the Banjo-Tooie client's)."""
        old = set(self.tags)
        if tag_link:
            self.tags.add("TagLink")
        else:
            self.tags.discard("TagLink")
        if old != self.tags and self.server and not self.server.socket.closed:
            await self.send_msgs([{"cmd": "ConnectUpdate", "tags": self.tags}])

    async def send_tag_link(self) -> None:
        """A tag for the other players, in the Banjo-Tooie client's form (BTClient.py:506-516)."""
        if "TagLink" in self.tags and self.slot is not None:
            await self.send_msgs([{"cmd": "Bounce", "tags": ["TagLink"],
                                   "data": {"time": time.time(), "source": self.instance_id, "tag": True}}])

    def make_gui(self):
        base = super().make_gui()

        class BanjoKazooieManager(base):
            base_title = "Archipelago Banjo-Kazooie Client"

        return BanjoKazooieManager

    def slot_seed(self) -> Optional[int]:
        """The seed to commit, once connected to a slot and its items are in (or none came in ITEMS_GRACE: the
        server sends ReceivedItems only when there is an item). Writing before them would take back what the
        game holds and give it again."""
        if self.slot is None or not self.slot_data:
            return None
        if not self.items_ready and time.monotonic() - self.connected_at < ITEMS_GRACE:
            return None
        seed = self.slot_data.get("seed")
        return seed if isinstance(seed, int) and 0 < seed <= 0xFFFFFFFF else None

    def wanted_items(self) -> hack.Items:
        items, skipped = ids.items_of(NAME_OF_ID.get(item.item) for item in self.items_received)
        for name in skipped:
            if ("skipped", name) not in self.told:
                self.told.add(("skipped", name))
                logger.info(f"The hack has nothing for {name or 'an item this world does not know'} yet: "
                            f"the game gets nothing for it.")
        return items

    # poll asks these, and the combined client (worlds/banjo_kazooie_tooie) answers them its own way, with the
    # attributes poll uses (link, link_driver, last_state, told, sent) and slot_seed and wanted_items.

    def bk_settings(self) -> Tuple[bool, bool, bool]:
        """skip_intro, notesanity and skip_lair_cutscene, as the slot's data has them."""
        return (bool(self.slot_data.get("skip_intro", True)), bool(self.slot_data.get("notesanity", False)),
                bool(self.slot_data.get("skip_lair_cutscene", True)))

    def bk_exits(self) -> Optional[List[hack.Exit]]:
        """The exit map for the slot's world doors (slot data "world_entrances"; none for a slot without them).
        None when they put no world behind each door: the client then writes nothing, as the game would play
        another order of the worlds than the server's logic."""
        try:
            return ids.exits_of(self.slot_data.get("world_entrances"))
        except ValueError as exc:
            if ("exits", str(exc)) not in self.told:
                self.told.add(("exits", str(exc)))
                logger.error(f"This slot's world doors are not a world behind each door ({exc}): generate it again.")
            return None

    def bk_traps(self) -> Optional[Tuple[int, ...]]:
        """The traps of each kind given to BK: every one received, in this world."""
        return ids.traps_of(NAME_OF_ID.get(item.item) for item in self.items_received)

    def bk_link_inbox(self) -> None:
        """Deaths and tags received for BK are owed as they arrive (on_deathlink, on_package)."""

    async def bk_link_sent(self, sent: Sent) -> None:
        """What the game did by itself: Banjo's deaths and his D-pad left swaps, for the other players."""
        for _ in range(sent.deaths):
            if "DeathLink" in self.tags:
                await self.send_death(f"{self.player_names.get(self.slot, 'Banjo')} fell in Banjo-Kazooie.")
        for _ in range(sent.tags):
            await self.send_tag_link()

    async def bk_goal(self) -> None:
        """The game shows Gruntilda beaten."""
        if not self.finished_game:
            self.finished_game = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            logger.info("Gruntilda is beaten: goal sent.")


def _new_emulator():
    # the emu_loader package, else the copy this world carries (client/emu.py)
    return load_emu_loader().EmuLoaderClient(validation_func=hack.validate, pull_from_web=False)


def _rdram_base(emu) -> Optional[int]:
    return getattr(emu.emulator_info, "connected_offset", None)


async def poll(ctx: BanjoKazooieContext, emu) -> hack.Tick:
    """One look at the game: write what it should hold, send what it shows."""
    seed = ctx.slot_seed()
    exits = ctx.bk_exits() if seed else []
    if exits is None:
        seed, exits = None, []
    items = ctx.wanted_items() if seed else hack.Items()
    skip_intro, notesanity, skip_lair_cutscene = ctx.bk_settings()
    tick = ctx.link.tick(emu, seed, skip_intro, items, notesanity, skip_lair_cutscene, exits)
    if tick.state != ctx.last_state:
        ctx.last_state = tick.state
        log = logger.error if tick.state == "refused" else logger.info
        log(f"Banjo-Kazooie: {tick.reason}")
    if tick.committed and ("committed", seed) not in ctx.told:
        ctx.told.add(("committed", seed))
        logger.info(f"Gave the game this slot's seed and items: {hack.describe(items)}")
    if tick.state != "ready" or ctx.slot is None:
        return tick
    locations = set()
    for check in tick.checks:
        location = ids.location_of(*check)
        if location is not None:
            locations.add(location)
        elif ("unknown", check) not in ctx.told:
            ctx.told.add(("unknown", check))
            logger.debug(f"The game shows {hack.check_names([check])[0]}, which is no location of this world.")
    ctx.locations_checked |= locations      # CommonClient sends these again after a reconnect
    new = (locations & ctx.missing_locations) - ctx.sent
    if new:
        ctx.sent |= new
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])
    if tick.goal:
        await ctx.bk_goal()
    if ctx.link.found is not None:
        ctx.bk_link_inbox()
        sent = ctx.link_driver.step(emu, ctx.link.found, ctx.bk_traps())
        if sent.deaths or sent.tags:
            await ctx.bk_link_sent(sent)
    return tick


async def emulator_loop(ctx: BanjoKazooieContext) -> None:
    loop = asyncio.get_running_loop()
    logger.info("Looking for an emulator running Banjo-Kazooie (Project64 or ares, with the hack's ROM or the "
                "dual-boot image; while Tooie runs, the client waits for Banjo-Kazooie).")
    rescanner = None    # a second client for looking elsewhere, made once (emu_loader logs every making)
    while not ctx.exit_event.is_set():
        ctx.emu_status = "looking for an emulator running Banjo-Kazooie"
        emu = await loop.run_in_executor(None, _new_emulator)
        while not emu.is_connected() and not ctx.exit_event.is_set():
            await asyncio.sleep(ATTACH_RETRY)
            await loop.run_in_executor(None, emu.connect)
        if ctx.exit_event.is_set():
            break
        name = getattr(emu.emulator_info, "readable_emulator_name", "an emulator")
        ctx.emu_status = f"attached to {name}"
        logger.info(f"Attached to {name}.")
        ctx.link = hack.Link()
        ctx.last_state = None
        away_since = None
        last_rescan = time.monotonic()
        try:
            while not ctx.exit_event.is_set():
                tick = await poll(ctx, emu)
                now = time.monotonic()
                away_since = (away_since or now) if tick.state == "waiting" else None
                if away_since and now - away_since > RESCAN_AFTER and now - last_rescan > RESCAN_AFTER:
                    # BK has not been at this RAM for a while: Tooie runs, or the emulator loaded the ROM again at
                    # another place. Look again, and keep this one unless BK is found elsewhere.
                    last_rescan = now
                    if rescanner is None:
                        rescanner = await loop.run_in_executor(None, _new_emulator)
                    else:
                        await loop.run_in_executor(None, rescanner.connect)
                    if rescanner.is_connected() and _rdram_base(rescanner) != _rdram_base(emu):
                        logger.info("Found Banjo-Kazooie at another place in the emulator's memory.")
                        emu.disconnect()
                        emu, rescanner, away_since = rescanner, None, None
                        ctx.link = hack.Link()
                    elif rescanner.is_connected():
                        rescanner.disconnect()
                await asyncio.sleep(POLL)
        except Exception as e:
            logger.exception(f"Lost the emulator ({e}); looking for it again.", extra={"compact_gui": True})
        try:
            emu.disconnect()
        except Exception:
            pass
        ctx.emu_status = "not attached"
        ctx.link = hack.Link()
        await asyncio.sleep(1.0)

def main(*args: str) -> None:
    Utils.init_logging("BanjoKazooieClient", exception_logger="Client")
    parser = get_base_parser(description="Banjo-Kazooie client: the hack's ROM in an emulator, and a server.")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    parsed = handle_url_arg(parser.parse_args(args), parser=parser)

    async def _main() -> None:
        ctx = BanjoKazooieContext(parsed.connect, parsed.password)
        ctx.auth = parsed.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        ctx.emulator_task = asyncio.create_task(emulator_loop(ctx), name="emulator loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        Utils.async_start(rom.patch_and_run(ctx.rom_settings, ctx.rom_target()), name="patch")
        await ctx.exit_event.wait()
        ctx.server_address = None
        await ctx.shutdown()
        try:
            await asyncio.wait_for(ctx.emulator_task, timeout=3.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

    import colorama
    colorama.just_fix_windows_console()
    asyncio.run(_main())
    colorama.deinit()


if __name__ == "__main__":
    main()
