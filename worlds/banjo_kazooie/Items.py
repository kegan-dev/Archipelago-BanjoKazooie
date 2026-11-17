"""Item definitions for Banjo-Kazooie.

Mirrors Archipelago-BanjoTooie/worlds/banjo_tooie/Items.py: ItemData(id, qty, classification), category
tables merged into all_item_table.
"""

from typing import Dict, NamedTuple

from BaseClasses import Item, ItemClassification

from .Names import itemName
from .Names.ids import item_id, jinjo_item_id, note_door_item_id


class BanjoKazooieItem(Item):
    game = "Banjo-Kazooie"


class ItemData(NamedTuple):
    bkid: int
    qty: int
    classification: ItemClassification


P = ItemClassification.progression
PS = ItemClassification.progression_skip_balancing
U = ItemClassification.useful
F = ItemClassification.filler
T = ItemClassification.trap

# Counts are vanilla totals. Verify against the per-level location tables as they are written. Notes are
# not items: they stay in the levels, and the note total reaching a door's cost is a location
# (Locations.NOTE_DOOR_table) while the door is an item (note_door_table below). item_id(1) was a Note
# placeholder until 2026-10-28.
collectable_table: Dict[str, ItemData] = {
    itemName.JIGGY: ItemData(item_id(0), 100, PS),
    # With notesanity only (Options.Notesanity): one per note, the hack's note totals the Notes received
    # (hack/bk/decomp/BKBT.md, "Notes kept, and notes as Archipelago locations").
    itemName.NOTE: ItemData(item_id(1), 900, PS),
    itemName.EMPTY_HONEYCOMB: ItemData(item_id(2), 24, U),
    # 115 ids, `enum mumbotoken_e` 1..0x73 (hack/bk/decomp/include/enums.h:1646-1763), the most the hack
    # reads from the client (BKBT_AP_TOKEN_MAX). The game places 116 tokens, but two of Mad Monster
    # Mansion's share id 0x3D (enums.h:1708): once one is picked up, the other despawns
    # (hack/bk/decomp/src/core2/ch/mumbotoken.c:77-83).
    itemName.MUMBO_TOKEN: ItemData(item_id(3), 115, PS),
}

# The 45 Jinjos, one per level and colour (Names/itemName.py): the client writes bkbt_ap_items.jinjos[hack id]
# (layout 0.10.0), and the level's five make its Jinjo jiggy appear beside Banjo there (hack/bk/decomp/BKBT.md,
# "Jinjos as Archipelago items and locations"). Each is placed at its own Jinjo unless they are shuffled
# (__init__.py, create_items).
jinjo_table: Dict[str, ItemData] = {
    name: ItemData(jinjo_item_id(hack_id), 1, PS) for name, hack_id in itemName.JINJOS.items()
}

moves_table: Dict[str, ItemData] = {
    itemName.CLIMB: ItemData(item_id(20), 1, P),
    itemName.SWIM: ItemData(item_id(21), 1, P),
    itemName.FEATHERY_FLAP: ItemData(item_id(22), 1, P),
    itemName.FLAP_FLIP: ItemData(item_id(23), 1, P),
    itemName.RATATAT_RAP: ItemData(item_id(24), 1, P),
    itemName.BEAK_BARGE: ItemData(item_id(25), 1, P),
    itemName.ROLL: ItemData(item_id(26), 1, P),
    itemName.EGGS: ItemData(item_id(27), 1, P),
    itemName.TALON_TROT: ItemData(item_id(28), 1, P),
    itemName.BEAK_BUSTER: ItemData(item_id(29), 1, P),
    itemName.SHOCK_JUMP: ItemData(item_id(30), 1, P),
    itemName.FLIGHT: ItemData(item_id(31), 1, P),
    itemName.WONDERWING: ItemData(item_id(32), 1, P),
    itemName.WADING_BOOTS: ItemData(item_id(33), 1, P),
    itemName.BEAK_BOMB: ItemData(item_id(34), 1, P),
    itemName.TURBO_TROT: ItemData(item_id(35), 1, P),
    itemName.CLAW_SWIPE: ItemData(item_id(36), 1, P),
    itemName.TALL_JUMP: ItemData(item_id(37), 1, P),
}

# Moves taught on Spiral Mountain. Camera control is taught there too but is not an item. The pool takes
# its moves from the molehills that are locations (Locations.vanilla_molehill_moves).
SM_TUTORIAL_MOVES = [
    itemName.CLIMB, itemName.SWIM, itemName.FEATHERY_FLAP, itemName.FLAP_FLIP,
    itemName.RATATAT_RAP, itemName.BEAK_BARGE, itemName.ROLL, itemName.CLAW_SWIPE, itemName.TALL_JUMP,
]

# The note doors 1..8, one item each: with it the door opens when Banjo next comes near it, and without it
# the door stays shut whatever the notes (hack/bk/decomp/BKBT.md, "Note doors as Archipelago items and
# locations"; the client writes bkbt_ap_items.note_doors[door], layout 0.8.0). A door's item joins the pool
# with the first level behind the door (the owner's decision of 2026-10-28; __init__.py, create_items).
note_door_table: Dict[str, ItemData] = {
    name: ItemData(note_door_item_id(door), 1, P) for door, name in enumerate(itemName.NOTE_DOORS, start=1)
}

filler_table: Dict[str, ItemData] = {
    itemName.EXTRA_LIFE: ItemData(item_id(100), 0, F),
    itemName.BLUE_EGG_REFILL: ItemData(item_id(101), 0, F),
    itemName.RED_FEATHER_REFILL: ItemData(item_id(102), 0, F),
    itemName.GOLD_FEATHER_REFILL: ItemData(item_id(103), 0, F),
}

# The traps, at 110 + their kind (Names/ids.py): drawn as filler, at most max_traps of them (__init__.py,
# get_filler_item_name); the client writes their totals into the hack's link block (client/ids.py, traps_of)
trap_table: Dict[str, ItemData] = {
    name: ItemData(item_id(110 + kind), 0, T) for kind, name in enumerate(itemName.TRAPS)
}

all_item_table: Dict[str, ItemData] = {
    **collectable_table,
    **jinjo_table,
    **moves_table,
    **note_door_table,
    **filler_table,
    **trap_table,
}

all_group_table: Dict[str, Dict[str, ItemData]] = {
    "Collectables": collectable_table,
    "Jinjos": jinjo_table,
    "Moves": moves_table,
    "Note Doors": note_door_table,
    "Filler": filler_table,
    "Traps": trap_table,
}

assert len({d.bkid for d in all_item_table.values()}) == len(all_item_table), "duplicate item id"
