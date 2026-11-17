"""Banjo-Kazooie Archipelago world.

Structure mirrors Archipelago-BanjoTooie/worlds/banjo_tooie/__init__.py. The whole game, with every kind of
check the ROM hack publishes (jiggies, Mumbo tokens, empty honeycombs, molehills, the note doors' thresholds), on
Lighthouse's logic (Rules.py). The client is BKClient.py, with the hack's contract in client/. See docs/ROADMAP.md for
what is still missing.
"""

from typing import Any, ClassVar, Dict, List, Optional, Set, TextIO, Union

import settings
from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch

from .Entrances import identity
from .Items import BanjoKazooieItem, ItemData, all_group_table, all_item_table, trap_table
from .Locations import NOTE_DOOR_COSTS, BanjoKazooieLocation, LocationData, all_location_table
from .Names import itemName
from .Options import BanjoKazooieOptions
from .Pool import create_pool, place_molehill_moves
from .Presets import options_presets
from .Regions import connect_regions, create_regions, draw_world_entrances
from .Rules import NOTES_IN_WORLD, NoteGroup, Rule, set_rules


def slot_data(world: Any) -> Dict[str, Any]:
    """What the client writes into the game (client/hack.py): the seed it commits the settings with, which a save
    is then bound to (never 0: the hack takes 0 for "no client"; hack/bk/decomp/BKBT.md, "The Archipelago
    settings"), the world behind each Lair door (door -> world, by level name; the client writes the hack's exit
    map from it, Entrances.exit_map), and the layout of the hack's anchor it expects. The combined world sends the
    same under "bk"."""
    return {
        "version": "0.0.1",
        "seed": world.client_seed,
        "skip_intro": bool(world.options.skip_intro),
        "skip_lair_cutscene": bool(world.options.skip_lair_cutscene),
        "notesanity": bool(world.options.notesanity),
        "world_entrances": dict(world.world_entrances),
        "layout": [0, 16],
        "logic_type": int(world.options.logic_type),
    }


def run_client(*args: str) -> None:
    from .BKClient import main  # lazy, so that generating needs nothing the client needs
    launch(main, name="Banjo-Kazooie Client", args=args)


components.append(Component("Banjo-Kazooie Client", func=run_client, component_type=Type.CLIENT,
                            game_name="Banjo-Kazooie", supports_uri=True,
                            description="Connects an Archipelago server to the Banjo-Kazooie hack in an emulator."))


class BanjoKazooieSettings(settings.Group):
    """The client makes the ROM it plays from your own Banjo-Kazooie ROM (client/rom.py), as the Banjo-Tooie client
    does: these say where it is, where the ROM goes and what to start it in."""

    class RomPath(settings.OptionalUserFilePath):
        """File path of the Banjo-Kazooie (USA) ROM, version 1.0."""

    class PatchPath(settings.OptionalUserFolderPath):
        """Folder path of where to save the patched ROM."""

    class ProgramPath(settings.OptionalUserFilePath):
        """
        File path of the program to automatically run (your emulator).
        Leave blank to disable.
        """

    class ProgramArgs(str):
        """
        Arguments to pass to the automatically run program.
        Leave blank to disable.
        """

    rom_path: RomPath | str = ""
    patch_path: PatchPath | str = ""
    program_path: ProgramPath | str = ""
    program_args: ProgramArgs | str = ""


class BanjoKazooieWeb(WebWorld):
    theme = "jungle"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Banjo-Kazooie for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Kegan McIlwaine"],
    )]
    options_presets = options_presets


class BanjoKazooieWorld(World):
    """
    Banjo-Kazooie is a 3D platformer by Rare for the Nintendo 64. Collect Jiggies, Notes, and Bottles'
    moves across nine worlds to open Gruntilda's Lair and rescue Tooty.
    """

    game = "Banjo-Kazooie"
    web = BanjoKazooieWeb()
    topology_present = True
    settings: ClassVar[BanjoKazooieSettings]

    options_dataclass = BanjoKazooieOptions
    options: BanjoKazooieOptions

    item_name_to_id: ClassVar[Dict[str, int]] = {name: data.bkid for name, data in all_item_table.items()}
    location_name_to_id: ClassVar[Dict[str, int]] = {name: data.bkid for name, data in all_location_table.items()}
    item_name_groups: ClassVar[Dict[str, Set[str]]] = {
        group: set(table.keys()) for group, table in all_group_table.items()
    }

    def __init__(self, multiworld, player):
        super().__init__(multiworld, player)
        self.enabled_location_names: Set[str] = set()
        self.note_groups: List[NoteGroup] = []  # Rules.note_groups, set by set_rules
        self.client_seed = 0                     # generate_early
        self.world_entrances: Dict[str, str] = identity()  # door -> the world behind it (connect_entrances)
        self.world_doors: Dict[Any, Any] = {}    # the doors' connections (Regions.connect_regions)
        self.entrance_draws = 0                  # the mappings the shuffle drew (Regions.draw_world_entrances)
        self.traps_in_pool = 0                   # create_item, for get_filler_item_name

    def generate_early(self) -> None:
        # The seed the client commits the game's settings with (fill_slot_data): drawn once, never 0.
        self.client_seed = self.random.randrange(1, 1 << 32)

    # -- locations ---------------------------------------------------------------------------------

    def location_enabled(self, name: str, data: LocationData) -> bool:
        # Molehills are always locations: in the hack a molehill teaches nothing and its move comes only
        # as an item, so even unshuffled moves are placed at their molehills (create_items). Jiggies are
        # always locations too: in the hack a jiggy picked up is a check and adds nothing to the jiggies
        # held, which come only from the items received (hack/bk/decomp/BKBT.md, "Jiggies as Archipelago
        # items and locations"), and so are Mumbo tokens, for the same reason ("Mumbo tokens as
        # Archipelago items and locations"); and so are empty honeycombs, whose health the hack gives only
        # from the honeycombs received ("Empty honeycombs as Archipelago items and locations"): unshuffled,
        # each holds its own honeycomb (create_items).
        # A note door's threshold only once the notes the world counts can reach its cost (Rules.NOTES_IN_WORLD;
        # every location must be reachable with every item): all eight, with the game's 900.
        if data.group == "Note Door" and NOTE_DOOR_COSTS[data.hack_id - 1] > NOTES_IN_WORLD:
            return False
        # The notes only with notesanity: the hack keeps every note picked up either way, and publishes it.
        if data.group == "Note" and not self.options.notesanity:
            return False
        self.enabled_location_names.add(name)
        return True

    def create_regions(self) -> None:
        create_regions(self)
        connect_regions(self)

    # -- what the module functions ask the world (Rules.py, "Lighthouse's expressions"): here, BK's own names ---

    def bk_item(self, name: str) -> str:
        return name

    def bk_region(self, name: str) -> Optional[str]:
        return name

    def bk_move(self, move: str) -> Union[str, Rule]:
        return move

    def bk_location(self, name: str, address: Optional[int], region: Region) -> Location:
        return BanjoKazooieLocation(self.player, name, address, region)

    def bk_event_item(self, event: str) -> Item:
        return BanjoKazooieItem(event, ItemClassification.progression, None, self.player)

    def bk_place_moves(self, pool: List[Item]) -> None:
        place_molehill_moves(self, pool)

    # -- items -------------------------------------------------------------------------------------

    def create_item(self, name: str, classification: Optional[ItemClassification] = None) -> Item:
        data: ItemData = all_item_table[name]
        if name in trap_table:
            self.traps_in_pool += 1
        return BanjoKazooieItem(name, classification or data.classification, data.bkid, self.player)

    # The filler's own weights against the traps' (the Banjo-Tooie world's way, its __init__.py:909-938): each of the
    # three refills weighs 25, and the traps weigh their options while fewer than max_traps are in the pool. Extra Life
    # is not drawn since 2026-11-11 (the owner's decision: lives are infinite), though it stays in the table, id kept.
    FILLER_WEIGHT = 25
    FILLER = (itemName.BLUE_EGG_REFILL, itemName.RED_FEATHER_REFILL, itemName.GOLD_FEATHER_REFILL)

    def get_filler_item_name(self) -> str:
        weights = [(name, self.FILLER_WEIGHT) for name in self.FILLER]
        if self.traps_in_pool < self.options.max_traps.value:
            o = self.options
            weights += list(zip(trap_table, (o.trip_trap_weight.value, o.slip_trap_weight.value,
                                             o.transform_trap_weight.value, o.squish_trap_weight.value,
                                             o.tip_trap_weight.value)))
        names, chances = zip(*weights)
        return self.random.choices(names, chances, k=1)[0]

    def create_items(self) -> None:
        pool = create_pool(self)        # Pool.py
        unfilled = len(self.multiworld.get_unfilled_locations(self.player))
        assert len(pool) <= unfilled, f"{len(pool)} progression items for {unfilled} locations"
        while len(pool) < unfilled:
            pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        set_rules(self)

    def connect_entrances(self) -> None:
        # After the rules and the items, which the draw checks every mapping against (Regions.draw_world_entrances).
        if self.options.randomize_world_entrances:
            self.entrance_draws = draw_world_entrances(self, self.random)

    def write_spoiler(self, spoiler_handle: TextIO) -> None:
        if self.world_entrances != identity():
            spoiler_handle.write(f"\n\nWorld doors ({self.multiworld.player_name[self.player]}):\n")
            for door, world in self.world_entrances.items():
                spoiler_handle.write(f"    {door} door -> {world}\n")

    # -- slot data ---------------------------------------------------------------------------------

    def fill_slot_data(self) -> Dict[str, Any]:
        # death link and tag link are this world's; the combined world sends Tooie's options for both games
        return {**slot_data(self), "death_link": bool(self.options.death_link),
                "tag_link": bool(self.options.tag_link)}
