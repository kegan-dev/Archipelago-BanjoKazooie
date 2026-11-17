"""Spiral Mountain's empty honeycombs and molehills: the ids the ROM hack publishes them under, and their rules,
which are Lighthouse's (Rules.py; docs/upstream-lighthouse.md)."""

import unittest

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from ..Items import SM_TUTORIAL_MOVES
from ..Locations import all_location_table, vanilla_molehill_moves
from ..Names import itemName, locationName, regionName
from ..Names.ids import honeycomb_location_id, molehill_location_id

# enum honeycomb_e, hack/bk/decomp/include/enums.h:1638-1643
SM_HONEYCOMB_HACK_IDS = {
    locationName.SM_HONEYCOMB_STUMP: 0x13,
    locationName.SM_HONEYCOMB_WATERFALL: 0x14,
    locationName.SM_HONEYCOMB_UNDERWATER: 0x15,
    locationName.SM_HONEYCOMB_TREE: 0x16,
    locationName.SM_HONEYCOMB_COLLIWOBBLE: 0x17,
    locationName.SM_HONEYCOMB_QUARRIES: 0x18,
}

# BKBT_AP_HONEYCOMB_SLOTS: bkbt_ap_locations.honeycombs[] has 0x19 bytes and byte 0 is never set
# (hack/bk/decomp/BKBT.md, "Empty honeycombs as Archipelago items and locations").
HONEYCOMB_SLOTS = 0x19

# The move bytes Spiral Mountain's molehills set, enum ability_e (hack/bk/decomp/src/SM/ch/smbottles.c,
# hack/bk/decomp/include/core2/abilityprogress.h:23-44), by molehill: 2, 3, 4 (three), 5, 6 (three), 7.
SM_MOLEHILL_HACK_IDS = {
    locationName.SM_MOLEHILL_CAMERA_CONTROL: 0x03,
    locationName.SM_MOLEHILL_SWIM: 0x0F,
    locationName.SM_MOLEHILL_CLAW_SWIPE: 0x04,
    locationName.SM_MOLEHILL_ROLL: 0x0C,
    locationName.SM_MOLEHILL_RATATAT: 0x0B,
    locationName.SM_MOLEHILL_BEAK_BARGE: 0x00,
    locationName.SM_MOLEHILL_FLAP_FLIP: 0x08,
    locationName.SM_MOLEHILL_TALL_JUMP: 0x0A,
    locationName.SM_MOLEHILL_FEATHERY_FLAP: 0x07,
    locationName.SM_MOLEHILL_CLIMB: 0x05,
}

# BKBT_AP_MOVE_COUNT: bkbt_ap_locations.moves[] has 20 bytes, one per enum ability_e
# (hack/bk/decomp/include/bkbt.h).
MOVE_COUNT = 20


def sm_locations(group: str):
    return {name: data for name, data in all_location_table.items()
            if data.group == group and data.region == regionName.SM}


class TestMolehillHackIds(unittest.TestCase):
    def test_spiral_mountain(self):
        self.assertEqual({name: data.hack_id for name, data in sm_locations("Molehill").items()}, SM_MOLEHILL_HACK_IDS)

    def test_every_move_is_taught_once(self):
        hack_ids = [data.hack_id for data in all_location_table.values() if data.group == "Molehill"]
        self.assertEqual(sorted(hack_ids), list(range(MOVE_COUNT)))

    def test_location_id_follows_the_move(self):
        for name, data in all_location_table.items():
            if data.group == "Molehill":
                self.assertEqual(data.bkid, molehill_location_id(data.hack_id), name)

    def test_vanilla_moves_cover_every_molehill_but_the_two_the_client_sends(self):
        sm_vanilla = {name: move for name, move in vanilla_molehill_moves.items() if name in SM_MOLEHILL_HACK_IDS}
        self.assertEqual(set(sm_vanilla) | {locationName.SM_MOLEHILL_CAMERA_CONTROL}, set(SM_MOLEHILL_HACK_IDS))
        self.assertEqual(sorted(sm_vanilla.values()), sorted(SM_TUTORIAL_MOVES))
        self.assertEqual(set(vanilla_molehill_moves),
                         {name for name, data in all_location_table.items() if data.group == "Molehill"}
                         - {locationName.SM_MOLEHILL_CAMERA_CONTROL, locationName.GL_MOLEHILL_NOTE_DOORS})


class TestSpiralMountainMolehills(BanjoKazooieTestBase):
    options = {
        "randomize_moves": True,
    }

    def test_one_location_per_move_taught(self):
        found = {location.name for location in self.world.get_region(regionName.SM).locations
                 if location.name in all_location_table and all_location_table[location.name].group == "Molehill"}
        self.assertEqual(found, set(SM_MOLEHILL_HACK_IDS))

    def test_spiral_mountains_moves_from_the_start(self):
        # start_with_spiral_mountain_moves, on by default: the nine at the start, none in the pool
        start = [item.name for item in self.multiworld.precollected_items[self.player]]
        pool = [item.name for item in self.multiworld.itempool]
        for move in SM_TUTORIAL_MOVES:
            self.assertEqual(start.count(move), 1, move)
            self.assertNotIn(move, pool)
        # Ten moves taught, nine items: the client always sends camera control.
        self.assertEqual(len(SM_TUTORIAL_MOVES), len(SM_MOLEHILL_HACK_IDS) - 1)


class TestEveryMoveShuffled(BanjoKazooieRuleTestBase):
    options = BanjoKazooieRuleTestBase.every_move_shuffled

    def test_every_move_taught_is_in_the_pool_once_but_camera_control(self):
        pool = [item.name for item in self.multiworld.itempool]
        for move in SM_TUTORIAL_MOVES:
            self.assertEqual(pool.count(move), 1, move)
        self.assertFalse([item.name for item in self.multiworld.precollected_items[self.player]
                          if item.name in SM_TUTORIAL_MOVES])


class TestHoneycombHackIds(unittest.TestCase):
    def test_spiral_mountain(self):
        self.assertEqual({name: data.hack_id for name, data in sm_locations("Honeycomb").items()},
                         SM_HONEYCOMB_HACK_IDS)

    def test_every_honeycomb_indexes_the_published_array(self):
        hack_ids = [data.hack_id for data in all_location_table.values() if data.group == "Honeycomb"]
        self.assertEqual(sorted(hack_ids), list(range(1, HONEYCOMB_SLOTS)))

    def test_location_id_follows_the_hack_id(self):
        for name, data in all_location_table.items():
            if data.group == "Honeycomb":
                self.assertEqual(data.bkid, honeycomb_location_id(data.hack_id), name)


class TestSpiralMountainHoneycombRules(BanjoKazooieRuleTestBase):
    """Lighthouse's rules (Lighthouse/src/port/Rando/Logic/Regions/SpiralMountain.cpp:10-15). Only the listed
    location is checked: without these moves other checks go too."""
    options = {
        **BanjoKazooieRuleTestBase.every_move_shuffled,
        "randomize_honeycombs": True,
    }

    def test_colliwobble_needs_rat_a_tat_rap(self):
        self.assertAccessDependency([locationName.SM_HONEYCOMB_COLLIWOBBLE], [[itemName.RATATAT_RAP]],
                                    only_check_listed=True)

    def test_stump_needs_flap_flip(self):
        self.assertAccessDependency([locationName.SM_HONEYCOMB_STUMP], [[itemName.FLAP_FLIP]], only_check_listed=True)

    def test_waterfall_needs_a_longer_jump(self):
        # Lighthouse's CAN_EXTEND_JUMP_DISTANCE (Logic.h:373-375)
        self.assertAccessDependency(
            [locationName.SM_HONEYCOMB_WATERFALL],
            [[itemName.FEATHERY_FLAP], [itemName.RATATAT_RAP], [itemName.TALON_TROT]], only_check_listed=True)

    def test_tree_needs_climb_or_flap_flip(self):
        self.assertAccessDependency([locationName.SM_HONEYCOMB_TREE], [[itemName.CLIMB], [itemName.FLAP_FLIP]],
                                    only_check_listed=True)

    def test_underwater_needs_swim(self):
        self.assertAccessDependency([locationName.SM_HONEYCOMB_UNDERWATER], [[itemName.SWIM]], only_check_listed=True)

    def test_quarries_need_something_that_breaks_a_boulder(self):
        # Lighthouse's CAN_BREAK_OBJECT(RA_BREAK_OBJECT_BOULDER) (Logic.h:295-299)
        self.assertAccessDependency(
            [locationName.SM_HONEYCOMB_QUARRIES],
            [[itemName.BEAK_BARGE], [itemName.EGGS], [itemName.BEAK_BUSTER], [itemName.WONDERWING]],
            only_check_listed=True)
