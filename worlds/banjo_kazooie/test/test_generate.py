from unittest import TestCase

from . import BanjoKazooieTestBase, check_presets
from .. import BanjoKazooieWorld
from ..Items import SM_TUTORIAL_MOVES, moves_table
from ..Locations import vanilla_molehill_moves
from ..Names import locationName
from ..Presets import ALPHA


class TestDefaultGeneration(BanjoKazooieTestBase):
    """Default options must produce a beatable skeleton world."""


class TestAllShuffled(BanjoKazooieTestBase):
    options = {
        "randomize_moves": True,
        "randomize_honeycombs": True,
        "randomize_jinjos": True,
    }


class TestAlphaPreset(BanjoKazooieTestBase):
    """The alpha's template (Presets.ALPHA): a full seed on it (Archipelago's default tests), the moves shuffled with
    Spiral Mountain's nine from the start."""
    options = ALPHA

    def test_spiral_mountains_moves_from_the_start(self):
        start = [item.name for item in self.multiworld.precollected_items[self.player]]
        pool = [item.name for item in self.multiworld.itempool]
        for move in SM_TUTORIAL_MOVES:
            self.assertEqual(start.count(move), 1, move)
            self.assertNotIn(move, pool)
        self.assertTrue([move for move in moves_table if move in pool])     # the other moves shuffled


class TestPresets(TestCase):
    def test_presets_are_options(self):
        check_presets(self, BanjoKazooieWorld)


class TestHoneycombsWithoutMoves(BanjoKazooieTestBase):
    """Honeycombs shuffled, moves not: each molehill gives its own move, as in the vanilla game."""
    options = {
        "randomize_honeycombs": True,
    }

    def test_each_molehill_gives_its_move(self):
        for loc_name, move in vanilla_molehill_moves.items():
            location = self.world.get_location(loc_name)
            self.assertEqual(location.item and location.item.name, move, loc_name)
            self.assertTrue(location.locked, loc_name)

    def test_no_move_from_the_start_or_in_the_pool(self):
        precollected = self.multiworld.precollected_items[self.player]
        self.assertFalse([item.name for item in precollected if item.name in moves_table])
        self.assertFalse([item.name for item in self.multiworld.itempool if item.name in moves_table])

    def test_colliwobble_after_the_attack_molehill(self):
        self.assertFalse(self.can_reach_location(locationName.SM_HONEYCOMB_COLLIWOBBLE))
        self.collect(self.world.get_location(locationName.SM_MOLEHILL_RATATAT).item)
        self.assertTrue(self.can_reach_location(locationName.SM_HONEYCOMB_COLLIWOBBLE))
