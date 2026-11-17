"""Location definitions for Banjo-Kazooie.

LocationData(id, hack_id, group, region). `hack_id` is the index under which the ROM hack publishes the check, in
the array of `bkbt_ap_locations` (hack/bk/decomp/include/bkbt.h, behind the BK anchor's +0x14) that the group
names:

    "Honeycomb"   honeycombs[hack_id], hack_id an `enum honeycomb_e`, 1..0x18 (layout 0.5.0)
    "Jiggy"       jiggies[hack_id], hack_id an `enum jiggy_e`, 1..0x64 (layout 0.6.0)
    "Molehill"    moves[hack_id], hack_id the `enum ability_e` the lesson teaches (layout 0.4.0)
    "Mumbo Token" tokens[hack_id], hack_id an `enum mumbotoken_e`, 1..0x73 (layout 0.7.0)
    "Note Door"   note_doors[hack_id], hack_id the door's number, 1..8 (layout 0.8.0)
    "Jinjo"       jinjos[hack_id], hack_id (`enum level_e` - 1) * 5 + the colour's bit, 0..49 (layout 0.10.0)
    "Note"        bit hack_id of notes[], hack_id (`enum level_e` - 1) * 100 + the note's number in its level, 0..999
                  (layout 0.11.0; with notesanity only)

The game is the only writer of those bytes and bits and the client only reads them: not 0 means checked
(hack/bk/decomp/BKBT.md, "Empty honeycombs as Archipelago items and locations", "Jiggies as Archipelago items and
locations", "Mumbo tokens as Archipelago items and locations", "Note doors as Archipelago items and locations",
"Jinjos as Archipelago items and locations" and "Molehills as Archipelago locations"). Beak Barge's and Mumbo's
Mountain's blue Jinjo's hack ids are 0, so never test a hack id's truth.

Every kind the hack publishes, for the whole game: the jiggies, Mumbo tokens, empty honeycombs, molehills and
Jinjos come from LogicData.LOCATIONS, generated from Lighthouse's checks (tools/lighthouse_logic.py), with their
regions and Lighthouse's rules (Rules.py applies them); the note doors' thresholds are the world's own (below).
Notes are counted (Notes.py) and, with notesanity, locations too (below); Stop 'n' Swop has nothing in the hack.
Spiral Mountain's attack and jump molehills teach three moves each, one location per move, and the Lair's Bottles
(the note-door lesson) and Spiral Mountain's camera-control molehill teach moves the client always sends, so they
hold ordinary items.
"""

from typing import Dict, NamedTuple, Optional

from BaseClasses import Location

from .LogicData import LOCATIONS
from .Names import itemName, locationName, regionName
from .Names.ids import (honeycomb_location_id, jiggy_location_id, jinjo_location_id, molehill_location_id,
                        note_door_location_id, note_location_id, token_location_id)
from .Notes import NOTES


class BanjoKazooieLocation(Location):
    game = "Banjo-Kazooie"


class LocationData(NamedTuple):
    bkid: int
    hack_id: Optional[int]
    group: str
    region: str


ID_OF_GROUP = {
    "Molehill": molehill_location_id,
    "Honeycomb": honeycomb_location_id,
    "Jiggy": jiggy_location_id,
    "Mumbo Token": token_location_id,
    "Jinjo": jinjo_location_id,
}

# Lighthouse's checks: (name, group, hack id, region, rule, Lighthouse check, the location's own item: a molehill's
# move, a Jinjo's Jinjo).
lighthouse_table: Dict[str, LocationData] = {
    name: LocationData(ID_OF_GROUP[group](hack_id), hack_id, group, region)
    for name, group, hack_id, region, _rule, _check, _move in LOCATIONS
}

# Each location's rule as Lighthouse has it, and the Lighthouse check it is (Rules.OVERRIDES is keyed by these).
lighthouse_rules = {name: rule for name, _g, _h, _r, rule, _c, _m in LOCATIONS}
lighthouse_checks = {name: check for name, _g, _h, _r, _rule, check, _m in LOCATIONS}

# The move each molehill location gives when moves are not shuffled, as in the vanilla game. Camera control and
# the note-door lesson have no item (the client always sends them), so their molehills hold ordinary items then.
vanilla_molehill_moves: Dict[str, str] = {name: move for name, group, *_rest, move in LOCATIONS
                                          if group == "Molehill" and move}

# The Jinjo each Jinjo location holds when Jinjos are not shuffled: itself, as in the vanilla game.
vanilla_jinjos: Dict[str, str] = {name: jinjo for name, group, *_rest, jinjo in LOCATIONS if group == "Jinjo"}

# The note doors' costs, by door number - 1: bkbt_note_door_costs (hack/bk/decomp/src/core1/code_0.c), the
# hack's copy of retail's note_door_cost_data (hack/bk/decomp/src/lair/lairspawnqueue.c:481), which the
# hack keeps. Doors 9..12 (828, 846, 864, 882) guard nothing and are not in the world (the owner's decision of
# 2026-10-28).
NOTE_DOOR_COSTS = (50, 180, 260, 350, 450, 640, 765, 810)

# The note doors' thresholds: door d's is checked once the note total (the worlds' best counts added up)
# has reached its cost, wherever Banjo is, and the hack publishes it as note_doors[d] (bkbt_apNoteDoors,
# hack/bk/decomp/src/core1/code_0.c; BKBT.md, "Note doors as Archipelago items and locations"). Since it
# belongs to no place in the game, it is in the Menu region; its rule is the notes (Rules.note_door_threshold).
NOTE_DOOR_table: Dict[str, LocationData] = {
    name: LocationData(note_door_location_id(door), door, "Note Door", regionName.MENU)
    for door, name in enumerate(locationName.NOTE_DOOR_THRESHOLDS, start=1)
}


def note_check(level: str, name: str) -> str:
    """The Lighthouse check of a note of Notes.NOTES (Rules.OVERRIDES is keyed by these)."""
    return f"RC_{regionName.LEVEL_PREFIX[level]}_NOTE_{name}"


_LEVEL_IDS = {name: level for level, name in itemName.JINJO_LEVELS.items()}  # a level's name -> enum level_e


def note_index(level: str, n: int) -> int:
    """The hack's index of note number `n` of `level`, BKBT_AP_NOTE_INDEX (hack/bk/decomp/include/bkbt.h)."""
    return (_LEVEL_IDS[level] - 1) * 100 + n


# The notes, locations with notesanity only (Options.Notesanity; __init__.py, location_enabled): one per row of
# Notes.NOTES, in its region, its hack id the note's index (published as a bit, bkbt_ap_locations.notes); its rule
# is Lighthouse's (Rules.set_rules, through note_rules and note_checks, so that Rules.OVERRIDES apply).
note_table: Dict[str, LocationData] = {
    location: LocationData(note_location_id(note_index(level, n)), note_index(level, n), "Note", region)
    for level, rows in NOTES.items() for _name, _map, _pos, region, _rule, n, location in rows
}
note_rules = {location: rule for rows in NOTES.values() for _n, _m, _p, _r, rule, _i, location in rows}
note_checks = {location: note_check(level, name)
               for level, rows in NOTES.items() for name, _m, _p, _r, _rule, _i, location in rows}

all_location_table: Dict[str, LocationData] = {**NOTE_DOOR_table, **lighthouse_table, **note_table}

# region name -> its locations
locations_by_region: Dict[str, Dict[str, LocationData]] = {}
for _name, _data in all_location_table.items():
    locations_by_region.setdefault(_data.region, {})[_name] = _data

assert len(all_location_table) == len(NOTE_DOOR_table) + len(lighthouse_table) + len(note_table), \
    "two locations share a name"
assert len({d.bkid for d in all_location_table.values()}) == len(all_location_table), "duplicate location id"
