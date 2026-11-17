"""ID allocation for the Banjo-Kazooie world.

Tooie uses hand-assigned absolute IDs in 1230046..1231640 and shares one number space between items and
locations. BK must stay disjoint so the combined world (docs/ROADMAP.md, Phase 2) can hold both tables.

Layout (all inclusive):
    1240000..1244999  items
    1245000..1249999  locations

Within the items, by offset: the collectables 0..3 (the Note, with notesanity, is 1), the moves 20..37, the note doors at 40 + the door's number
(41..48, note_door_item_id), the Jinjos at 50 + their hack id ((enum level_e - 1) * 5 + colour, 50..99 without the
Lair's 75..79, jinjo_item_id), the filler from 100 and the traps at 110 + their kind (110..114, since 2026-11-10). (10..14 were five Jinjos by colour, never in a pool, until
the Jinjos' build of 2026-10-29.)

Within the locations, by offset, each kind at a base + its hack id (the index the hack publishes it under,
Locations.py): the molehills at 20 + the move they teach (`enum ability_e`, 20..39, molehill_location_id), the
empty honeycombs at 60 + their `enum honeycomb_e` value (61..84, honeycomb_location_id), the jiggies at 100 +
their `enum jiggy_e` value (101..200, jiggy_location_id), the Mumbo tokens at 200 + their `enum mumbotoken_e`
value (201..315, token_location_id), the Jinjos at 320 + their hack id (320..369 without the Lair's 345..349,
jinjo_location_id), the note doors' thresholds at 400 + the door's number (401..408, note_door_location_id), and,
with notesanity, the notes at 1000 + their index ((enum level_e - 1) * 100 + their number in the level,
1000..1999 without the Lair's 1500..1599, note_location_id). (Until 2026-10-28 Spiral Mountain's honeycombs were 0..5 and the molehills 20..32 in
the order they were written.)

A door's number is its selector in the Lair's map setups, 1..12 by cost (1 is the 50-note door), the index
the hack publishes and reads it under (hack/bk/decomp/include/bkbt.h, BKBT_AP_NOTE_DOOR_SLOTS). Doors 9..12
guard nothing (docs/bk-decomp-notes.md, "Notes and note doors") and have no item or location yet.
"""

ITEM_BASE = 1240000
LOCATION_BASE = 1245000
ID_END = 1249999

MOLEHILL_LOCATION_OFFSET = 20  # + enum ability_e, 0..0x13 (hack/bk/decomp/include/core2/abilityprogress.h:23-44)
HONEYCOMB_LOCATION_OFFSET = 60  # + enum honeycomb_e, 1..0x18 (hack/bk/decomp/include/enums.h:1618-1644)
JIGGY_LOCATION_OFFSET = 100  # + enum jiggy_e, 1..0x64 (hack/bk/decomp/include/enums.h:1514-1616)
TOKEN_LOCATION_OFFSET = 200  # + enum mumbotoken_e, 1..0x73 (hack/bk/decomp/include/enums.h:1646-1763)
NOTE_DOOR_ITEM_OFFSET = 40  # + the door's number, 1..8
NOTE_DOOR_LOCATION_OFFSET = 400  # + the door's number, 1..8
NOTE_DOORS_IN_WORLD = 8  # doors 1..8: the ones that guard something
JINJO_ITEM_OFFSET = 50  # + the Jinjo's hack id, (enum level_e - 1) * 5 + colour (hack/bk/decomp/include/bkbt.h, BKBT_AP_JINJO_INDEX)
JINJO_LOCATION_OFFSET = 320  # + the same
LAIR_JINJOS = range(25, 30)  # BKBT_AP_JINJO_INDEX(LEVEL_6_LAIR, 0..4): the Lair has no Jinjos
NOTE_LOCATION_OFFSET = 1000  # + the note's index, BKBT_AP_NOTE_INDEX(level, n) = (level - 1) * 100 + n (hack/bk/decomp/include/bkbt.h)
NOTE_SLOTS = 1000  # BKBT_AP_NOTE_SLOTS: levels 1..0xA, 100 each
LAIR_NOTES = range(500, 600)  # BKBT_AP_NOTE_INDEX(LEVEL_6_LAIR, 0..99): the Lair has no notes


def item_id(offset: int) -> int:
    assert 0 <= offset < LOCATION_BASE - ITEM_BASE, offset
    return ITEM_BASE + offset


def location_id(offset: int) -> int:
    assert 0 <= offset <= ID_END - LOCATION_BASE, offset
    return LOCATION_BASE + offset


def molehill_location_id(move: int) -> int:
    """The location id of the molehill lesson of move `move` (`enum ability_e`)."""
    assert 0 <= move <= 0x13, hex(move)
    return location_id(MOLEHILL_LOCATION_OFFSET + move)


def honeycomb_location_id(honeycomb: int) -> int:
    """The location id of the empty honeycomb whose `enum honeycomb_e` value is `honeycomb`."""
    assert 1 <= honeycomb <= 0x18, hex(honeycomb)
    return location_id(HONEYCOMB_LOCATION_OFFSET + honeycomb)


def jiggy_location_id(jiggy: int) -> int:
    """The location id of the jiggy whose `enum jiggy_e` value is `jiggy`."""
    assert 1 <= jiggy <= 0x64, hex(jiggy)
    return location_id(JIGGY_LOCATION_OFFSET + jiggy)


def token_location_id(token: int) -> int:
    """The location id of the Mumbo token whose `enum mumbotoken_e` value is `token`."""
    assert 1 <= token <= 0x73, hex(token)
    return location_id(TOKEN_LOCATION_OFFSET + token)


def _jinjo(hack_id: int) -> int:
    assert 0 <= hack_id < 50 and hack_id not in LAIR_JINJOS, hack_id
    return hack_id


def jinjo_item_id(hack_id: int) -> int:
    """The item id of the Jinjo whose hack id is `hack_id`, (enum level_e - 1) * 5 + colour."""
    return item_id(JINJO_ITEM_OFFSET + _jinjo(hack_id))


def jinjo_location_id(hack_id: int) -> int:
    """The location id of the Jinjo whose hack id is `hack_id`: picking it up."""
    return location_id(JINJO_LOCATION_OFFSET + _jinjo(hack_id))


def note_location_id(index: int) -> int:
    """The location id of the note whose index is `index`, (enum level_e - 1) * 100 + its number in the level."""
    assert 0 <= index < NOTE_SLOTS and index not in LAIR_NOTES, index
    return location_id(NOTE_LOCATION_OFFSET + index)


def note_door_item_id(door: int) -> int:
    """The item id of note door number `door` (1 is the 50-note door)."""
    assert 1 <= door <= NOTE_DOORS_IN_WORLD, door
    return item_id(NOTE_DOOR_ITEM_OFFSET + door)


def note_door_location_id(door: int) -> int:
    """The location id of note door number `door`'s threshold: the note total reaching its cost."""
    assert 1 <= door <= NOTE_DOORS_IN_WORLD, door
    return location_id(NOTE_DOOR_LOCATION_OFFSET + door)
