"""The link's options (Options.py, from the Banjo-Tooie world's): traps take the place of filler in the pool, at most
max_traps of them, by their weights; death link and tag link go to the client in the slot data (client/link.py)."""

from BaseClasses import ItemClassification

from . import BanjoKazooieTestBase
from ..Items import filler_table, trap_table
from ..Names import itemName


class Seeded:
    """A fixed seed: the draws are random, and with the 11 filler slots of a pool with every move shuffled none would
    be a trap 1 time in 2000 at weight 100 against the filler's 100."""

    def world_setup(self, seed=None) -> None:
        super().world_setup(1)


def traps_in(test) -> list:
    return [item for item in test.multiworld.itempool if item.name in trap_table]


class TestNoTrapsByDefault(BanjoKazooieTestBase):
    def test_no_traps(self) -> None:
        self.assertEqual(traps_in(self), [])
        self.assertEqual(self.world.traps_in_pool, 0)

    def test_slot_data(self) -> None:
        data = self.world.fill_slot_data()
        self.assertEqual((data["death_link"], data["tag_link"]), (False, False))


class TestTraps(Seeded, BanjoKazooieTestBase):
    """With every move shuffled the pool has room for filler, and with max_traps above that every one may be a trap."""
    options = {"randomize_moves": True, "max_traps": 100, "death_link": True, "tag_link": True}

    def test_traps_take_filler(self) -> None:
        traps = traps_in(self)
        self.assertTrue(traps, "a pool with filler and max_traps 100 draws some traps")
        self.assertTrue(all(item.classification == ItemClassification.trap for item in traps))
        self.assertEqual(self.world.traps_in_pool, len(traps))

    def test_slot_data(self) -> None:
        data = self.world.fill_slot_data()
        self.assertEqual((data["death_link"], data["tag_link"]), (True, True))
        self.assertEqual(data["layout"], [0, 16])


class TestMaxTraps(Seeded, BanjoKazooieTestBase):
    """max_traps 1: once a trap is in the pool, the rest of the filler is filler."""
    options = {"randomize_moves": True, "max_traps": 1, "trip_trap_weight": 100}

    def test_at_most_one(self) -> None:
        self.assertEqual(len(traps_in(self)), 1)
        self.assertTrue([item for item in self.multiworld.itempool if item.name in filler_table])


class TestOneKind(Seeded, BanjoKazooieTestBase):
    """A kind of weight 0 is never drawn."""
    options = {"randomize_moves": True, "max_traps": 100, "trip_trap_weight": 0, "slip_trap_weight": 0,
               "transform_trap_weight": 0, "squish_trap_weight": 0, "tip_trap_weight": 100}

    def test_only_tips(self) -> None:
        self.assertEqual({item.name for item in traps_in(self)}, {itemName.TIP_TRAP})
