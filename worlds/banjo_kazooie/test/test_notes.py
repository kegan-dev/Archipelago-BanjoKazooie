"""The note doors' thresholds and items, and the notes the world counts towards them (Notes.py; Rules.py,
"Notes and the note doors' thresholds")."""

import unittest
from collections import Counter

from BaseClasses import CollectionState, ItemClassification

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from ..Items import note_door_table
from ..Locations import NOTE_DOOR_COSTS, NOTE_DOOR_table
from ..Names import itemName, locationName, regionName
from ..Names.ids import note_door_item_id, note_door_location_id
from ..Notes import NOTES
from ..Rules import NOTES_IN_WORLD, OVERRIDES, note_check, notes_in_logic, rule_of

# bkbt_note_door_costs, doors 1..8 of 12 (hack/bk/decomp/src/core1/code_0.c; retail
# hack/bk/decomp/src/lair/lairspawnqueue.c:481)
HACK_COSTS = (50, 180, 260, 350, 450, 640, 765, 810)

# BKBT_AP_NOTE_DOOR_SLOTS: bkbt_ap_locations.note_doors[] has 13 bytes, by the door's number, and byte 0 is
# never set (hack/bk/decomp/include/bkbt.h; BKBT.md, "Note doors as Archipelago items and locations").
NOTE_DOOR_SLOTS = 13


class TestNoteDoorTables(unittest.TestCase):
    def test_eight_door_items_by_number(self):
        self.assertEqual(list(note_door_table), [f"Note Door {door}" for door in range(1, 9)])
        for door, (name, data) in enumerate(note_door_table.items(), start=1):
            self.assertEqual(data.bkid, note_door_item_id(door), name)
            self.assertEqual(data.qty, 1, name)
            self.assertEqual(data.classification, ItemClassification.progression, name)

    def test_thresholds_index_the_published_array(self):
        self.assertEqual(list(NOTE_DOOR_table), [f"GL: Note Door {door} Threshold" for door in range(1, 9)])
        for door, (name, data) in enumerate(NOTE_DOOR_table.items(), start=1):
            self.assertEqual(data.group, "Note Door", name)
            self.assertEqual(data.hack_id, door, name)
            self.assertTrue(1 <= data.hack_id < NOTE_DOOR_SLOTS, name)
            self.assertEqual(data.bkid, note_door_location_id(door), name)

    def test_costs_are_the_hacks(self):
        self.assertEqual(NOTE_DOOR_COSTS, HACK_COSTS)


class TestNoteTable(unittest.TestCase):
    def test_every_level_has_its_hundred(self):
        self.assertEqual({level: len(notes) for level, notes in NOTES.items()}, {level: 100 for level in regionName.LEVELS})
        self.assertEqual(NOTES_IN_WORLD, 900)
        # the game spawns ten: the first hut's five in Mumbo's Mountain and in Bubblegloop Swamp
        self.assertEqual({level: sum(row[2] is None for row in notes) for level, notes in NOTES.items()
                          if any(row[2] is None for row in notes)}, {regionName.MM: 5, regionName.BGS: 5})

    def test_mumbos_mountain(self):
        notes = NOTES[regionName.MM]
        # placed: 85 outside, 6 inside Ticker's Tower, 4 in Mumbo's skull; the 5 of the first hut are not
        self.assertEqual(Counter(row[1] for row in notes if row[2] is not None), {0x02: 85, 0x0C: 6, 0x0E: 4})
        self.assertEqual([row[0] for row in notes if row[2] is None], [f"HUT_BUNDLE_{n}" for n in range(1, 6)])

    def test_mumbos_mountain_by_rule(self):
        # the owner's hand test of 2026-10-28: 77 with no move (73 outside, 4 in the skull), then 6 on the
        # huts' roofs and 5 from the first hut (their rules, Rules.OVERRIDES), 6 underwater and 6 in Ticker's
        # Tower (Lighthouse's)
        rules = Counter(repr(rule_of(note_check(regionName.MM, row[0]), row[4])) for row in NOTES[regionName.MM])
        self.assertEqual(sorted(rules.values()), [5, 6, 6, 6, 77])
        self.assertEqual(rules["True"], 77)
        self.assertEqual(rules[repr(("tokens", regionName.MM))], 6)
        self.assertEqual(rules[repr(("any", ("move", itemName.SWIM), ("tokens", regionName.MM)))], 6)

    def test_names_and_places_are_unique(self):
        for level, notes in NOTES.items():
            names = [row[0] for row in notes]
            self.assertEqual(len(names), len(set(names)), level)
            places = [(row[1], row[2]) for row in notes if row[2] is not None]
            self.assertEqual(len(places), len(set(places)), level)

    def test_every_note_override_is_a_note(self):
        checks = {note_check(level, row[0]) for level, notes in NOTES.items() for row in notes}
        for check in OVERRIDES:
            if "_NOTE_" in check:
                self.assertIn(check, checks)


class TestThresholdsInTheWorld(BanjoKazooieTestBase):
    """Default options: the game's 900 notes reach every door's cost."""

    def test_every_threshold_is_a_location(self):
        found = {location.name for location in self.world.get_region(regionName.MENU).locations}
        self.assertEqual(found, set(locationName.NOTE_DOOR_THRESHOLDS))

    def test_every_door_item_in_the_pool_once(self):
        pool = [item.name for item in self.multiworld.itempool]
        for door in note_door_table:
            self.assertEqual(pool.count(door), 1, door)

    def test_the_first_threshold_with_one_jiggy(self):
        first, second = locationName.NOTE_DOOR_THRESHOLDS[:2]
        self.assertFalse(self.can_reach_location(first))
        self.collect(self.get_item_by_name(itemName.JIGGY))
        self.assertTrue(self.can_reach_location(first))
        self.assertFalse(self.can_reach_location(second))


class TestNotesInLogic(BanjoKazooieRuleTestBase):
    """Every move shuffled, so that each is an item the state can hold or not."""
    options = BanjoKazooieRuleTestBase.every_move_shuffled

    def notes(self, *items: str, tokens: int = 0) -> int:
        state = CollectionState(self.multiworld)
        for name in items:
            state.collect(self.get_item_by_name(name))
        for token in self.get_items_by_name(itemName.MUMBO_TOKEN)[:tokens]:
            state.collect(token)
        return notes_in_logic(self.world, state)

    def test_none_before_mumbos_mountain(self):
        self.assertEqual(self.notes(itemName.BEAK_BUSTER, itemName.SWIM, tokens=5), 0)

    def test_seventy_seven_with_no_move(self):
        self.assertEqual(self.notes(itemName.JIGGY), 77)

    def test_the_huts_roofs_with_a_higher_jump(self):
        self.assertEqual(self.notes(itemName.JIGGY, itemName.TALL_JUMP), 83)
        self.assertEqual(self.notes(itemName.JIGGY, itemName.FLAP_FLIP), 83)
        self.assertEqual(self.notes(itemName.JIGGY, itemName.FEATHERY_FLAP), 77)

    def test_the_hut_with_beak_buster_from_its_roof(self):
        self.assertEqual(self.notes(itemName.JIGGY, itemName.BEAK_BUSTER), 77)
        self.assertEqual(self.notes(itemName.JIGGY, itemName.BEAK_BUSTER, itemName.TALL_JUMP), 88)
        self.assertEqual(self.notes(itemName.JIGGY, itemName.BEAK_BUSTER, itemName.FLAP_FLIP), 88)

    def test_the_underwater_caves_with_swim(self):
        self.assertEqual(self.notes(itemName.JIGGY, itemName.SWIM), 83)

    def test_the_termite_everywhere_but_the_hut(self):
        # four tokens are not the termite; five are: the tower, the roofs and the caves, not the hut's five (no
        # Beak Buster as the termite)
        self.assertEqual(self.notes(itemName.JIGGY, tokens=4), 77)
        self.assertEqual(self.notes(itemName.JIGGY, tokens=5), 95)
        self.assertEqual(self.notes(itemName.JIGGY, itemName.BEAK_BUSTER, tokens=5), 95)

    def test_all_hundred(self):
        self.assertEqual(self.notes(itemName.JIGGY, itemName.BEAK_BUSTER, itemName.TALL_JUMP, itemName.SWIM,
                                    tokens=5), 100)
