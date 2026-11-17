"""The world's ids for what the hack publishes and takes: (group, hack id) -> location id, and item name -> what the
client gives the game for it.

Built from the world's own tables, so they cannot drift apart: LogicData.LOCATIONS (each check's group and hack id,
generated from Lighthouse; Locations.lighthouse_table is made from the same rows), the note doors' thresholds
(Locations.NOTE_DOOR_table: door n's is note_doors[n], doors 1..8), the notes (Notes.NOTES: a note's bit is its
index, (enum level_e - 1) * 100 + its number; Locations.note_table) and the item names (Names/itemName.py).
test/test_client.py compares them with Items.all_item_table and Locations.all_location_table.

Only the world's pure modules are imported (no BaseClasses), so that a tool can load this with hack.py
(tools/bk_client_check.py).
"""

from collections import Counter
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from ..Entrances import exit_map
from ..LogicData import LOCATIONS
from ..Names import itemName
from ..Names.ids import (NOTE_DOORS_IN_WORLD, honeycomb_location_id, jiggy_location_id, jinjo_location_id,
                         molehill_location_id, note_door_location_id, note_location_id, token_location_id)
from ..Notes import NOTES
from .hack import REFILL_KINDS, TRAP_KINDS, Exit, Items

_ID_OF_GROUP = {
    "Molehill": molehill_location_id,
    "Honeycomb": honeycomb_location_id,
    "Jiggy": jiggy_location_id,
    "Mumbo Token": token_location_id,
    "Jinjo": jinjo_location_id,
}

# (group, hack id) -> location id, for every check the world has. A byte the game publishes that is not here
# (note doors 9..12, which guard nothing) is no location.
LOCATION_OF: Dict[Tuple[str, int], int] = {
    (group, hack_id): _ID_OF_GROUP[group](hack_id) for _name, group, hack_id, *_rest in LOCATIONS
}
LOCATION_OF.update({("Note Door", door): note_door_location_id(door) for door in range(1, NOTE_DOORS_IN_WORLD + 1)})
# The notes (with notesanity; the server ignores those its slot does not have, and the client sends only what it
# misses): a level's enum level_e from its name (Names/itemName.py, JINJO_LEVELS).
_LEVEL_IDS = {name: level for level, name in itemName.JINJO_LEVELS.items()}
LOCATION_OF.update({("Note", (_LEVEL_IDS[level] - 1) * 100 + row[5]): note_location_id((_LEVEL_IDS[level] - 1) * 100 + row[5])
                    for level, rows in NOTES.items() for row in rows})

# A move's item -> its enum ability_e: the hack id of the molehill that teaches it (LogicData.LOCATIONS' last
# field is the molehill's own move).
MOVE_OF: Dict[str, int] = {move: hack_id for _name, group, hack_id, _region, _rule, _check, move in LOCATIONS
                           if group == "Molehill" and move}

NOTE_DOOR_OF: Dict[str, int] = {name: door for door, name in enumerate(itemName.NOTE_DOORS, start=1)}

# A Jinjo's item -> its hack id, (enum level_e - 1) * 5 + colour (Names/itemName.py; the Jinjo locations' last
# field in LogicData.LOCATIONS is the same item).
JINJO_OF: Dict[str, int] = dict(itemName.JINJOS)

# A refill's item -> its kind in the items block (hack.REFILL_KINDS; include/bkbt.h, BKBT_AP_REFILL_*, since 0.16.0).
# The fourth kind, the less full feather, is Tooie's Feather Nest in the combined slot, which this world has no item for.
REFILL_OF: Dict[str, int] = {itemName.BLUE_EGG_REFILL: 0, itemName.RED_FEATHER_REFILL: 1, itemName.GOLD_FEATHER_REFILL: 2}

# Items the hack has nothing for: the client logs them and gives nothing. Lives are infinite since 2026-11-10, so the
# world no longer draws Extra Life (2026-11-11), but a seed generated before may hold some.
NOTHING_FOR = frozenset((itemName.EXTRA_LIFE,))


def location_of(group: str, hack_id: int) -> Optional[int]:
    return LOCATION_OF.get((group, hack_id))


# A trap's item -> its kind in the hack's link block (hack.TRAP_KINDS; Names/itemName.TRAPS is in the kinds' order)
TRAP_OF: Dict[str, int] = {name: kind for kind, name in enumerate(itemName.TRAPS)}


def traps_of(names: Iterable[Optional[str]]) -> Tuple[int, ...]:
    """The traps received of each kind, the totals the client writes into the link block."""
    counts = [0] * TRAP_KINDS
    for name in names:
        if name in TRAP_OF:
            counts[TRAP_OF[name]] += 1
    return tuple(counts)


def items_of(names: Iterable[Optional[str]]) -> Tuple[Items, Counter]:
    """What the game should hold for the items received, every copy counted (a jiggy is a jiggy, progression or
    useful), and the names the hack has nothing for, counted (None for an id the world does not know)."""
    moves, doors, jinjos, totals, skipped = set(), set(), set(), Counter(), Counter()
    refills = [0] * REFILL_KINDS
    for name in names:
        if name in MOVE_OF:
            moves.add(MOVE_OF[name])
        elif name in NOTE_DOOR_OF:
            doors.add(NOTE_DOOR_OF[name])
        elif name in JINJO_OF:
            jinjos.add(JINJO_OF[name])
        elif name in (itemName.EMPTY_HONEYCOMB, itemName.JIGGY, itemName.MUMBO_TOKEN, itemName.NOTE):
            totals[name] += 1
        elif name in REFILL_OF:
            refills[REFILL_OF[name]] += 1
        elif name in TRAP_OF:
            pass                        # the link's, traps_of
        else:
            skipped[name] += 1
    return Items(frozenset(moves), totals[itemName.EMPTY_HONEYCOMB], totals[itemName.JIGGY],
                 totals[itemName.MUMBO_TOKEN], frozenset(doors), frozenset(jinjos), totals[itemName.NOTE],
                 tuple(refills)), skipped


def exits_of(world_entrances: Optional[Mapping[str, str]]) -> List[Exit]:
    """The hack's exit map for the slot's doors (slot data "world_entrances", door -> the world behind it, by level
    name; Entrances.exit_map): none for a slot without them (a world before the shuffle) or with every door its own.
    Raises ValueError for a mapping that does not put each world behind one door."""
    if not world_entrances:
        return []
    return [Exit(*entry) for entry in exit_map(world_entrances)]
