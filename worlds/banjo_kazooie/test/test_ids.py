"""ID range invariants that must hold forever (see Names/ids.py and docs/ROADMAP.md)."""

import unittest

from ..Items import all_item_table
from ..Locations import all_location_table
from ..Names.ids import ID_END, ITEM_BASE, LOCATION_BASE

BT_ID_MIN, BT_ID_MAX = 1230046, 1231640  # Archipelago-BanjoTooie, Locations.py:11


class TestIdRanges(unittest.TestCase):
    def test_items_in_range(self):
        for name, data in all_item_table.items():
            self.assertTrue(ITEM_BASE <= data.bkid < LOCATION_BASE, name)

    def test_locations_in_range(self):
        for name, data in all_location_table.items():
            self.assertTrue(LOCATION_BASE <= data.bkid <= ID_END, name)

    def test_disjoint_from_tooie(self):
        for data in list(all_item_table.values()) + list(all_location_table.values()):
            self.assertFalse(BT_ID_MIN <= data.bkid <= BT_ID_MAX)
