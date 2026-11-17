"""The filler (2026-11-11, the owner's next item 3): the three refills, each filling its count in the game; Extra Life
is not drawn any more (lives are infinite), though it keeps its item and id."""

from collections import Counter

from . import BanjoKazooieTestBase
from ..Items import all_item_table, filler_table
from ..Names import itemName
from .test_link import Seeded

REFILLS = {itemName.BLUE_EGG_REFILL, itemName.RED_FEATHER_REFILL, itemName.GOLD_FEATHER_REFILL}


class TestFiller(Seeded, BanjoKazooieTestBase):
    """With every move shuffled the pool has 11 filler slots: all refills, no Extra Life."""
    options = {"randomize_moves": True}

    def test_the_pool_has_refills_only(self) -> None:
        filler = [item.name for item in self.multiworld.itempool if item.name in filler_table]
        self.assertTrue(filler)
        self.assertLessEqual(set(filler), REFILLS)

    def test_each_refill_is_drawn(self) -> None:
        drawn = Counter(self.world.get_filler_item_name() for _ in range(600))
        self.assertEqual(set(drawn), REFILLS)
        for name in REFILLS:
            self.assertGreater(drawn[name], 120, name)      # a third each: 200 of 600 on average

    def test_extra_life_keeps_its_id(self) -> None:
        self.assertIn(itemName.EXTRA_LIFE, all_item_table)
        self.assertEqual(self.world.item_name_to_id[itemName.EXTRA_LIFE], 1240100)
