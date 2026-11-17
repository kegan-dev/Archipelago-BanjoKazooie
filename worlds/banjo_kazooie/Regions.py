"""Region graph for Banjo-Kazooie: Lighthouse's regions and connections (LogicData.py, generated from the
Lighthouse/ submodule by tools/lighthouse_logic.py), entered from Menu at Spiral Mountain.

Lighthouse's events (switches, podiums, note doors, Gruntilda beaten) are event locations in their
regions, each holding an event item of the event's name, which rules ask for (Rules.compile_rule). Lighthouse's
entrance rules ask only for items and events; the world's own for a Lair form also ask that its Mumbo's skull be
reached (Rules.lair_tree: the crypt's), and an entrance whose rule asks for a region gets its indirect condition.
Menu also holds the note doors' thresholds, which are checked wherever Banjo is and so belong to no place
(Locations.NOTE_DOOR_table).

The nine world doors (Entrances.DOORS) are two connections each, named for the door ("<world> Door", from the door's
Lair region, with the door's rule) and for the world ("<world> Way Out", back to the door that leads into it):
connect_regions makes them by world.world_entrances, and apply_world_entrances points them elsewhere when the
world-entrance shuffle draws another mapping (__init__.py, connect_entrances).

Every region goes through world.bk_region (Rules.py): the BK world keeps them all, and the combined world
(worlds/banjo_kazooie_tooie) leaves Spiral Mountain out and puts Menu's thresholds in the Lair's lobby. A region
the world maps elsewhere is not made; one it leaves out takes its locations, events and connections with it.
"""

from random import Random
from typing import TYPE_CHECKING, Dict, Optional

from BaseClasses import CollectionState, Entrance, Region
from Options import OptionError

from .Entrances import DOOR_OF, DOORS, LEVELS, identity
from .Locations import locations_by_region
from .LogicData import CONNECTIONS, EVENTS, REGIONS, START
from .Names import regionName
from .Rules import compile_rule, event_location_name, lair_tree, region_terms, rule_of

if TYPE_CHECKING:
    from . import BanjoKazooieWorld


def create_regions(world: "BanjoKazooieWorld") -> None:
    create_region_shells(world)
    create_locations(world)
    create_events(world)


def create_region_shells(world: "BanjoKazooieWorld") -> None:
    player = world.player
    multiworld = world.multiworld
    for name in [regionName.MENU] + [region for region, _level, _map in REGIONS]:
        if world.bk_region(name) == name:
            multiworld.regions.append(Region(name, player, multiworld))


def create_locations(world: "BanjoKazooieWorld") -> None:
    for region_name, table in locations_by_region.items():
        target = world.bk_region(region_name)
        if target is None:
            continue
        region = world.get_region(target)
        for loc_name, data in table.items():
            if not world.location_enabled(loc_name, data):
                continue
            region.locations.append(world.bk_location(loc_name, data.bkid, region))


def create_events(world: "BanjoKazooieWorld") -> None:
    for region_name, event, _rule in EVENTS:
        target = world.bk_region(region_name)
        if target is None:
            continue
        region = world.get_region(target)
        location = world.bk_location(event_location_name(region_name, event), None, region)
        location.place_locked_item(world.bk_event_item(event))
        region.locations.append(location)


def door_name(level: str) -> str:
    return f"{level} Door"


def way_out_name(level: str) -> str:
    return f"{level} Way Out"


# The doors' two connections in LogicData.CONNECTIONS: (source, target) -> (the door's world, which of the two)
_DOOR_EDGES = {**{(door.door_region, door.entry_region): (door.level, "door") for door in DOORS},
               **{(door.entry_region, door.door_region): (door.level, "out") for door in DOORS}}


def connect_regions(world: "BanjoKazooieWorld") -> None:
    """Lighthouse's connections, the doors' as world.world_entrances says (retail without it). Keeps the doors' 18
    entrances in world.world_doors, by (level, "door" or "out")."""
    mapping = getattr(world, "world_entrances", None) or identity()
    inverse = {behind: door for door, behind in mapping.items()}
    world.world_doors = {}
    _connect(world, regionName.MENU, START, None)
    for frm, to, tree in CONNECTIONS:
        tree = lair_tree(rule_of(None, tree), frm)
        name = None
        edge = _DOOR_EDGES.get((frm, to))
        if edge is not None:
            level, which = edge
            if which == "door":
                name, to = door_name(level), DOOR_OF[mapping[level]].entry_region
            else:
                name, to = way_out_name(level), DOOR_OF[inverse[level]].door_region
        entrance = _connect(world, frm, to, compile_rule(world, tree), name)
        if entrance is None:
            continue
        if edge is not None:
            world.world_doors[edge] = entrance
        for region in region_terms(tree):
            target = world.bk_region(region)
            if target is not None:
                world.multiworld.register_indirect_condition(world.get_region(target), entrance)


def apply_world_entrances(world: "BanjoKazooieWorld", mapping) -> None:
    """Point the doors' connections as `mapping` (door -> the world behind it) says: door d's into the world behind
    it, each world's way out back to the door that leads into it. The rules stay the doors' own."""
    inverse = {behind: door for door, behind in mapping.items()}
    for door in DOORS:
        _repoint(world, world.world_doors[(door.level, "door")], DOOR_OF[mapping[door.level]].entry_region)
        _repoint(world, world.world_doors[(door.level, "out")], DOOR_OF[inverse[door.level]].door_region)
    world.world_entrances = dict(mapping)
    state = getattr(world.multiworld, "state", None)
    if state is not None:
        state.stale[world.player] = True     # its regions reached were worked out with the old doors


# How many mappings draw_world_entrances tries before it gives up.
DRAWS = 2000


def draw_world_entrances(world: "BanjoKazooieWorld", rng: Random) -> int:
    """The world-entrance shuffle: a mapping door -> world drawn with `rng` until every one of the player's locations
    is reached with all of the player's items (their pool, their start items, and the items locked in their places,
    which the sweep collects where they are reached), and applied. Some mappings never are: without the moves
    shuffled Mumbo's Mountain's molehill teaches Talon Trot, which the first note door needs, so another world behind
    the first door leaves the rest of the game shut. The draws taken; OptionError after DRAWS."""
    multiworld, player = world.multiworld, world.player
    pool = [item for item in multiworld.itempool if item.player == player]
    locations = multiworld.get_locations(player)
    for draw in range(1, DRAWS + 1):
        worlds = list(LEVELS)
        rng.shuffle(worlds)
        mapping: Dict[str, str] = dict(zip(LEVELS, worlds))
        apply_world_entrances(world, mapping)
        state = CollectionState(multiworld)
        for item in pool:
            state.collect(item, True)
        state.sweep_for_advancements(locations)
        if all(location.can_reach(state) for location in locations):
            return draw
    apply_world_entrances(world, identity())
    raise OptionError(f"{multiworld.player_name[player]}: no order of the world doors reached every place in "
                      f"{DRAWS} draws")


def _repoint(world: "BanjoKazooieWorld", entrance: Entrance, to: str) -> None:
    region = world.get_region(world.bk_region(to))
    if entrance.connected_region is region:
        return
    entrance.connected_region.entrances.remove(entrance)
    entrance.connect(region)


def _connect(world: "BanjoKazooieWorld", frm: str, to: str, rule, name: Optional[str] = None) -> Optional[Entrance]:
    source, target = world.bk_region(frm), world.bk_region(to)
    if source is None or target is None:
        return None
    return world.get_region(source).connect(world.get_region(target), name, rule)
