"""Treasure Trove Cove: the rules the world takes over Lighthouse's (Rules.OVERRIDES)."""

from BaseClasses import CollectionState

from . import BanjoKazooieRuleTestBase
from ..Names import itemName, locationName

SANDCASTLE = "Treasure Trove Cove: Inside the Sandcastle"  # a region of LogicData.REGIONS


class TestTreasureTroveCoveRules(BanjoKazooieRuleTestBase):
    """Every move shuffled. Only the listed locations are checked: without these moves other checks go too."""
    options = BanjoKazooieRuleTestBase.every_move_shuffled

    def test_eggs_and_beak_buster_for_the_sandcastle_jiggy(self):
        # The letters take a Beak Buster only once Leaky has drained the water (Rules.OVERRIDES, 2026-10-29).
        self.assertAccessDependency([locationName.TTC_JIGGY_SANDCASTLE], [[itemName.EGGS]], only_check_listed=True)
        self.assertAccessDependency([locationName.TTC_JIGGY_SANDCASTLE], [[itemName.BEAK_BUSTER]],
                                    only_check_listed=True)

    def test_dive_gets_banjo_in_but_not_the_jiggy(self):
        state = CollectionState(self.multiworld)
        self.collect_all_but([itemName.EGGS], state)
        self.assertTrue(state.can_reach_region(SANDCASTLE, self.player))
        self.assertFalse(state.can_reach_location(locationName.TTC_JIGGY_SANDCASTLE, self.player))
