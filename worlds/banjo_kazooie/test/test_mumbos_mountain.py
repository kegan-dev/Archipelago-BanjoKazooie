"""Mumbo's Mountain and the Lair's first room: the jiggies', Mumbo tokens' and molehills' hack ids against the
decomp and BK_Randomizer's flag records, the world-entry costs of the Lair's pictures, Mumbo's prices, and the
rules of the owner's hand tests (Rules.OVERRIDES) over Lighthouse's."""

import unittest

from BaseClasses import CollectionState

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from ..Locations import all_location_table
from ..Names import itemName, locationName, regionName
from ..Names.ids import jiggy_location_id, token_location_id
from ..Rules import JIGGIES_FOR_GRUNTYS_DOOR, JIGGIES_TO_OPEN, TOKENS_TO_TRANSFORM

# enum jiggy_e, hack/bk/decomp/include/enums.h:1516-1525, 1566-1567
JIGGY_HACK_IDS = {
    locationName.MM_JIGGY_JINJOS: 0x01,
    locationName.MM_JIGGY_TICKERS_TOWER: 0x02,
    locationName.MM_JIGGY_MUMBOS_SKULL: 0x03,
    locationName.MM_JIGGY_JUJU: 0x04,
    locationName.MM_JIGGY_HUTS: 0x05,
    locationName.MM_JIGGY_RUINS: 0x06,
    locationName.MM_JIGGY_HILL: 0x07,
    locationName.MM_JIGGY_ORANGE_PADS: 0x08,
    locationName.MM_JIGGY_CHIMPY: 0x09,
    locationName.MM_JIGGY_CONGA: 0x0A,
    locationName.GL_JIGGY_FIRST: 0x33,
    locationName.GL_JIGGY_MM_WITCH_SWITCH: 0x34,
}

# The placed ones' Flag records in BK_Randomizer/Randomization_Processes/Dicts_And_Lists/Flagged_Objects.py
# (:31-46, :710-713): the record id + 1 is the enum jiggy_e value (docs/bk-decomp-notes.md, "Jiggies").
FLAG_RECORDS = {
    locationName.MM_JIGGY_TICKERS_TOWER: 0x01,
    locationName.MM_JIGGY_MUMBOS_SKULL: 0x02,
    locationName.MM_JIGGY_RUINS: 0x05,
    locationName.MM_JIGGY_HILL: 0x06,
    locationName.GL_JIGGY_FIRST: 0x32,
}

# enum mumbotoken_e, hack/bk/decomp/include/enums.h:1648-1652
TOKEN_HACK_IDS = {
    locationName.MM_TOKEN_STUMP_NEAR_CONGA: 0x01,
    locationName.MM_TOKEN_BEHIND_RUINS: 0x02,
    locationName.MM_TOKEN_UNDER_RAMP_TO_MUMBOS_SKULL: 0x03,
    locationName.MM_TOKEN_BEHIND_PINK_JINJO: 0x04,
    locationName.MM_TOKEN_INSIDE_TICKERS_TOWER: 0x05,
}

# Their Flag records in Flagged_Objects.py (:48-67): the record id less 199 is the enum mumbotoken_e value
# (hack/bk/decomp/src/core2/ch/mumbotoken.c:45-60).
TOKEN_FLAG_RECORDS = {
    locationName.MM_TOKEN_STUMP_NEAR_CONGA: 0xC8,
    locationName.MM_TOKEN_BEHIND_RUINS: 0xC9,
    locationName.MM_TOKEN_UNDER_RAMP_TO_MUMBOS_SKULL: 0xCA,
    locationName.MM_TOKEN_BEHIND_PINK_JINJO: 0xCB,
    locationName.MM_TOKEN_INSIDE_TICKERS_TOWER: 0xCC,
}

# enum ability_e (hack/bk/decomp/include/core2/abilityprogress.h:23-44) of molehills 0xA..0xC
# (hack/bk/decomp/src/core2/ch/mole.c:62-64)
MM_MOLEHILL_HACK_IDS = {
    locationName.MM_MOLEHILL_EGGS: 0x06,
    locationName.MM_MOLEHILL_BEAK_BUSTER: 0x02,
    locationName.MM_MOLEHILL_TALON_TROT: 0x10,
}


def in_level(prefix: str, group: str):
    return {name: data.hack_id for name, data in all_location_table.items()
            if name.startswith(prefix + ": ") and data.group == group}


class TestHackIds(unittest.TestCase):
    def test_mumbos_mountain_and_the_lairs_first_two_jiggies(self):
        found = {name: hid for name, hid in {**in_level("MM", "Jiggy"), **in_level("GL", "Jiggy")}.items()
                 if name in JIGGY_HACK_IDS}
        self.assertEqual(found, JIGGY_HACK_IDS)
        self.assertEqual(set(in_level("MM", "Jiggy")), {n for n in JIGGY_HACK_IDS if n.startswith("MM")})

    def test_placed_jiggies_are_their_flag_record_plus_one(self):
        for name, record in FLAG_RECORDS.items():
            self.assertEqual(all_location_table[name].hack_id, record + 1, name)

    def test_tokens(self):
        self.assertEqual(in_level("MM", "Mumbo Token"), TOKEN_HACK_IDS)
        for name, record in TOKEN_FLAG_RECORDS.items():
            self.assertEqual(all_location_table[name].hack_id, record - 199, name)
            self.assertEqual(all_location_table[name].bkid, token_location_id(record - 199), name)

    def test_molehills(self):
        self.assertEqual(in_level("MM", "Molehill"), MM_MOLEHILL_HACK_IDS)

    def test_jiggy_location_ids(self):
        for name, hack_id in JIGGY_HACK_IDS.items():
            self.assertEqual(all_location_table[name].bkid, jiggy_location_id(hack_id), name)


class TestWorldEntryCosts(unittest.TestCase):
    def test_cumulative_picture_costs(self):
        self.assertEqual(JIGGIES_TO_OPEN, {
            regionName.MM: 1, regionName.TTC: 3, regionName.CC: 8, regionName.BGS: 15, regionName.FP: 23,
            regionName.GV: 32, regionName.MMM: 42, regionName.RBB: 54, regionName.CCW: 69,
        })

    def test_gruntys_door(self):
        self.assertEqual(JIGGIES_FOR_GRUNTYS_DOOR, 94)

    def test_cumulative_transformation_prices(self):
        self.assertEqual(TOKENS_TO_TRANSFORM, {
            regionName.MM: 5, regionName.BGS: 15, regionName.FP: 30, regionName.MMM: 50, regionName.CCW: 75,
        })


class TestMumbosMountainEntry(BanjoKazooieTestBase):
    """Default options: moves at their own molehills."""

    def test_one_jiggy_opens_mumbos_mountain(self):
        self.assertTrue(self.can_reach_region(regionName.GL))
        self.assertFalse(self.can_reach_region(regionName.MM))
        self.collect(self.get_item_by_name(itemName.JIGGY))
        self.assertTrue(self.can_reach_region(regionName.MM))

    def test_the_first_jiggy_needs_nothing(self):
        self.assertTrue(self.can_reach_location(locationName.GL_JIGGY_FIRST))

    def test_each_mumbos_mountain_molehill_gives_its_move(self):
        for loc_name, move in {locationName.MM_MOLEHILL_EGGS: itemName.EGGS,
                               locationName.MM_MOLEHILL_BEAK_BUSTER: itemName.BEAK_BUSTER,
                               locationName.MM_MOLEHILL_TALON_TROT: itemName.TALON_TROT}.items():
            location = self.world.get_location(loc_name)
            self.assertEqual(location.item and location.item.name, move, loc_name)
            self.assertTrue(location.locked, loc_name)


class TestMumbosMountainJinjos(BanjoKazooieRuleTestBase):
    """Every move and every Jinjo shuffled: a Jinjo counts only in its own level, and the five give the jiggy."""
    options = {**BanjoKazooieRuleTestBase.every_move_shuffled, "randomize_jinjos": True}
    five = itemName.JINJOS_OF_LEVEL[regionName.MM]

    def test_the_jinjo_jiggy_needs_the_five(self):
        self.assertAccessDependency([locationName.MM_JIGGY_JINJOS], [list(self.five)], only_check_listed=True)
        for jinjo in self.five:
            state = CollectionState(self.multiworld)
            self.collect_all_but([jinjo], state)
            self.assertFalse(state.can_reach_location(locationName.MM_JIGGY_JINJOS, self.player), jinjo)

    def test_other_levels_jinjos_do_not_count(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but(list(self.five), state)
        self.assertFalse(state.can_reach_location(locationName.MM_JIGGY_JINJOS, self.player))

    def test_the_green_jinjo_takes_the_hut_break(self):
        # in a hut (Rules.OVERRIDES, the owner's hand test of 2026-10-28)
        self.assertAccessDependency([locationName.MM_JINJO_GREEN], [[itemName.TALL_JUMP], [itemName.FLAP_FLIP]],
                                    only_check_listed=True)
        self.assertAccessDependency([locationName.MM_JINJO_GREEN], [[itemName.BEAK_BUSTER]], only_check_listed=True)

    def test_the_jinjo_ids(self):
        # (enum level_e - 1) * 5 + the colour's bit (hack/bk/decomp/include/bkbt.h, BKBT_AP_JINJO_INDEX)
        for name, hack_id in {locationName.MM_JINJO_BLUE: 0, locationName.MM_JINJO_GREEN: 1, locationName.MM_JINJO_ORANGE: 2,
                              locationName.MM_JINJO_PINK: 3, locationName.MM_JINJO_YELLOW: 4}.items():
            self.assertEqual(all_location_table[name].hack_id, hack_id, name)


class TestMumbosMountainRules(BanjoKazooieRuleTestBase):
    """Every move shuffled. Only the listed locations are checked: without these moves other checks go too."""
    options = BanjoKazooieRuleTestBase.every_move_shuffled

    def test_a_higher_jump_for_the_huts_the_jinjos_and_the_juju(self):
        # The owner's hand test of 2026-10-28 (Rules.OVERRIDES); Lighthouse asks less.
        self.assertAccessDependency(
            [locationName.MM_JIGGY_HUTS, locationName.MM_JIGGY_JINJOS, locationName.MM_JIGGY_JUJU],
            [[itemName.TALL_JUMP], [itemName.FLAP_FLIP]], only_check_listed=True)

    def test_beak_buster_for_the_huts_and_the_jinjos(self):
        self.assertAccessDependency([locationName.MM_JIGGY_HUTS, locationName.MM_JIGGY_JINJOS],
                                    [[itemName.BEAK_BUSTER]], only_check_listed=True)

    def test_eggs_for_the_juju(self):
        self.assertAccessDependency([locationName.MM_JIGGY_JUJU], [[itemName.EGGS]], only_check_listed=True)

    def test_a_higher_jump_for_the_token_in_tickers_tower(self):
        # The owner's tries (Rules.OVERRIDES); Lighthouse: Flap Flip, Talon Trot or the termite.
        self.assertAccessDependency(
            [locationName.MM_TOKEN_INSIDE_TICKERS_TOWER],
            [[itemName.TALL_JUMP], [itemName.FLAP_FLIP], [itemName.FEATHERY_FLAP], [itemName.RATATAT_RAP]],
            only_check_listed=True)

    def test_flap_flip_for_the_token_near_conga_and_mumbos_skull(self):
        # The owner's check of 2026-10-27, and Lighthouse's (MumbosMountain.cpp:18, :31)
        self.assertAccessDependency([locationName.MM_TOKEN_STUMP_NEAR_CONGA, locationName.MM_JIGGY_MUMBOS_SKULL],
                                    [[itemName.FLAP_FLIP]], only_check_listed=True)

    def test_the_termite_takes_five_tokens(self):
        state = CollectionState(self.multiworld)
        state.collect(self.get_item_by_name(itemName.JIGGY))
        tokens = self.get_items_by_name(itemName.MUMBO_TOKEN)
        for token in tokens[:4]:
            state.collect(token)
        self.assertFalse(state.can_reach(locationName.MM_JIGGY_TICKERS_TOWER, "Location", self.player))
        state.collect(tokens[4])
        self.assertTrue(state.can_reach(locationName.MM_JIGGY_TICKERS_TOWER, "Location", self.player))

    def test_the_rest_with_one_jiggy_and_no_move(self):
        state = CollectionState(self.multiworld)
        state.collect(self.get_item_by_name(itemName.JIGGY))
        for name in (locationName.MM_JIGGY_RUINS, locationName.MM_JIGGY_HILL, locationName.MM_JIGGY_ORANGE_PADS,
                     locationName.MM_TOKEN_BEHIND_RUINS, locationName.MM_TOKEN_UNDER_RAMP_TO_MUMBOS_SKULL,
                     locationName.MM_TOKEN_BEHIND_PINK_JINJO, locationName.MM_MOLEHILL_BEAK_BUSTER,
                     locationName.MM_MOLEHILL_TALON_TROT):
            self.assertTrue(state.can_reach(name, "Location", self.player), name)
