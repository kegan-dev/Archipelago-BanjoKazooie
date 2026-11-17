"""Notesanity (Options.Notesanity): each of the 900 notes a location, 900 Notes in the pool, and the note doors'
thresholds counting the Notes received (hack/bk/decomp/BKBT.md, "Notes kept, and notes as Archipelago
locations"); without it, no note location and no Note."""

from collections import Counter

from BaseClasses import CollectionState, ItemClassification

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from ..Items import all_item_table
from ..Locations import NOTE_DOOR_COSTS, all_location_table, note_index, note_table
from ..Names import itemName, locationName
from ..Names.ids import LAIR_NOTES, NOTE_LOCATION_OFFSET, item_id, location_id
from ..Notes import NOTES


class TestNoteTable(BanjoKazooieTestBase):
    """The note locations as the hack numbers them (BKBT_AP_NOTE_INDEX, hack/bk/decomp/include/bkbt.h)."""
    run_default_tests = False

    def test_one_location_per_note(self):
        self.assertEqual(len(note_table), 900)
        self.assertEqual(Counter(index // 100 + 1 for index in (data.hack_id for data in note_table.values())),
                         {level: 100 for level in (1, 2, 3, 4, 5, 7, 8, 9, 10)})
        for name, data in note_table.items():
            self.assertEqual(data.group, "Note", name)
            self.assertNotIn(data.hack_id, LAIR_NOTES, name)
            self.assertEqual(data.bkid, location_id(NOTE_LOCATION_OFFSET + data.hack_id), name)

    def test_the_huts_five_come_last(self):
        # BKBT_AP_HUT_NOTE_FIRST: the hut's notes are n 95..99 of Mumbo's Mountain and Bubblegloop Swamp
        for level in ("Mumbo's Mountain", "Bubblegloop Swamp"):
            huts = sorted(row[5] for row in NOTES[level] if row[2] is None)
            self.assertEqual(huts, list(range(95, 100)), level)
        self.assertEqual(note_index("Mumbo's Mountain", 95), 95)
        self.assertEqual(note_index("Bubblegloop Swamp", 99), 399)
        self.assertEqual(note_index("Mad Monster Mansion", 0), 900)

    def test_the_note_item(self):
        self.assertEqual(all_item_table[itemName.NOTE].bkid, item_id(1))


class TestWithoutNotesanity(BanjoKazooieTestBase):
    def test_no_note_location_and_no_note(self):
        self.assertFalse([loc for loc in self.multiworld.get_locations(self.player) if loc.name in note_table])
        self.assertNotIn(itemName.NOTE, [item.name for item in self.multiworld.itempool])

    def test_slot_data(self):
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["notesanity"], slot_data["layout"]), (False, [0, 16]))
        self.assertTrue(slot_data["skip_lair_cutscene"])        # on by default (Options.SkipLairCutscene)


class TestNotesanity(BanjoKazooieTestBase):
    options = {"notesanity": True}

    def test_every_note_is_a_location(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertTrue(set(note_table) <= names)

    def test_nine_hundred_notes_in_the_pool(self):
        notes = [item for item in self.multiworld.itempool if item.name == itemName.NOTE]
        self.assertEqual(len(notes), 900)
        # the most a threshold asks (door 8's 810) are progression, as the jiggies beyond Grunty's door are not
        self.assertEqual(Counter(item.classification for item in notes),
                         {ItemClassification.progression_skip_balancing: max(NOTE_DOOR_COSTS),
                          ItemClassification.useful: 900 - max(NOTE_DOOR_COSTS)})

    def test_thresholds_count_the_notes_received(self):
        notes = self.get_items_by_name(itemName.NOTE)
        for door, cost in enumerate(NOTE_DOOR_COSTS, start=1):
            threshold = locationName.NOTE_DOOR_THRESHOLDS[door - 1]
            state = CollectionState(self.multiworld)
            self.collect_all_but([itemName.NOTE], state)
            for note in notes[:cost - 1]:
                state.collect(note, True)
            self.assertFalse(state.can_reach_location(threshold, self.player), (door, cost - 1))
            state.collect(notes[cost - 1], True)
            self.assertTrue(state.can_reach_location(threshold, self.player), (door, cost))

    def test_slot_data(self):
        self.assertTrue(self.world.fill_slot_data()["notesanity"])


class TestNotesanityRules(BanjoKazooieRuleTestBase):
    """Every move shuffled: a note location asks what Lighthouse asks, or the owner's rule (Rules.OVERRIDES)."""
    options = {**BanjoKazooieRuleTestBase.every_move_shuffled, "notesanity": True}

    def test_the_huts_notes_take_the_hut_break(self):
        # the owner's hand test of 2026-10-28: the Beak Buster from a hut's roof, reached with Tall Jump or Flap Flip
        first_hut = [row[6] for row in NOTES["Mumbo's Mountain"] if row[0].startswith("HUT_BUNDLE_")]
        self.assertEqual(len(first_hut), 5)
        self.assertAccessDependency(first_hut, [[itemName.BEAK_BUSTER]], only_check_listed=True)
        self.assertAccessDependency(first_hut, [[itemName.TALL_JUMP], [itemName.FLAP_FLIP]], only_check_listed=True)

    def test_the_sandcastle_notes_take_the_drain_or_a_dive(self):
        # Lighthouse's: TreasureTroveCove.cpp:142-145
        inside = [row[6] for row in NOTES["Treasure Trove Cove"] if row[0].startswith("SANDCASTLE_INTERIOR_")]
        self.assertEqual(len(inside), 4)
        self.assertAccessDependency(inside, [[itemName.EGGS], [itemName.SWIM]], only_check_listed=True)
