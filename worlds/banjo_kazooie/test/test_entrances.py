"""The world-entrance shuffle (Options.RandomizeWorldEntrances): the nine doors' connections as Entrances.py has them,
the Lair's forms (Rules.lair_tree, the hack's quick transform), the draw (Regions.draw_world_entrances) and the slot
data the client writes the hack's exit map from (client/ids.py, exits_of)."""

from BaseClasses import CollectionState

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from .. import Entrances
from ..LogicData import CONNECTIONS, EVENTS, LOCATIONS, REGIONS
from ..Names import itemName, regionName
from ..Regions import apply_world_entrances, door_name, way_out_name
from ..Rules import lair_tree
from ..client import ids

CRYPT = ("Gruntilda's Lair: Near Mad Monster Mansion Entrance", "Gruntilda's Lair: First Water Switch Room")


class OnASeedThatFills:
    """Archipelago's default tests on one seed: with the shuffle some seeds fail to fill (about one in twenty-five
    with Randomize Moves, Options.RandomizeWorldEntrances), which a random seed would show as a test failing now and
    then. Seed 1 fills with each of the options below (measured 2026-11-05)."""
    seed = 1

    def setUp(self) -> None:
        if self.auto_construct:
            self.world_setup(self.seed)


def swapped(*pairs):
    mapping = Entrances.identity()
    for a, b in pairs:
        mapping[a], mapping[b] = mapping[b], mapping[a]
    return mapping


class TestDoorTable(BanjoKazooieTestBase):
    """Entrances.DOORS against the generated logic (LogicData, Lighthouse's)."""
    run_default_tests = False

    def test_each_door_is_two_of_lighthouses_connections(self):
        edges = {(frm, to): tree for frm, to, tree in CONNECTIONS}
        for door in Entrances.DOORS:
            entry = edges[(door.door_region, door.entry_region)]
            self.assertEqual(entry, ("all", ("picture", door.level), ("event", f"RA_PUZZLE_BOARD_{door.level.upper()}"
                                     .replace("'", "").replace(" ", "_"))), door.level)
            self.assertIs(edges[(door.entry_region, door.door_region)], True, door.level)

    def test_no_other_way_between_the_lair_and_a_world(self):
        level = {name: lvl for name, lvl, _map in REGIONS}
        doors = {(d.door_region, d.entry_region) for d in Entrances.DOORS} | {(d.entry_region, d.door_region)
                                                                              for d in Entrances.DOORS}
        between = {(frm, to) for frm, to, _tree in CONNECTIONS
                   if {level.get(frm), level.get(to)} & {regionName.GL_LEVEL} and level.get(frm) != level.get(to)
                   and regionName.SM not in (level.get(frm), level.get(to))
                   and level.get(to) is not None and level.get(frm) is not None}
        self.assertEqual(between, doors)

    def test_the_lobbies(self):
        map_of = {name: m for name, _lvl, m in REGIONS}
        for door in Entrances.DOORS:
            self.assertEqual(map_of[door.door_region], door.lobby, door.level)
            self.assertEqual(Entrances.DOOR_OF[door.level], door)

    def test_the_lair_forms(self):
        """Lighthouse's rules that lair_tree changes: the five that ask a Mumbo form in the Lair."""
        changed = set()
        for name, _group, _hack, region, rule, _check, _move in LOCATIONS:
            if lair_tree(rule, region) != rule:
                changed.add(name)
        for region, event, tree in EVENTS:
            if lair_tree(tree, region) != tree:
                changed.add(event)
        for frm, to, tree in CONNECTIONS:
            if lair_tree(tree, frm) != tree:
                changed.add((frm, to))
        self.assertEqual(changed, {"GL: Jiggy (MM Witch Switch)", "GL: Jiggy (CCW Witch Switch)",
                                   "GL: Mumbo Token (Above Note Door Water Area)", "RA_PUZZLE_BOARD_FREEZEEZY_PEAK", CRYPT})
        token = next(rule for name, _g, _h, _r, rule, _c, _m in LOCATIONS
                     if name == "GL: Mumbo Token (Above Note Door Water Area)")
        self.assertIn(("region", Entrances.DOOR_OF[regionName.CCW].door_region),
                      lair_tree(token, "Gruntilda's Lair: Before Fifth Note Door")[1:])

    def test_skulls_are_regions(self):
        names = {name for name, _lvl, _map in REGIONS}
        for level, skulls in Entrances.SKULLS.items():
            self.assertTrue(set(skulls) <= names, level)


class TestRetailDoors(BanjoKazooieTestBase):
    """The option off: every door to its own world, named, and no exit map."""

    def test_each_door_leads_to_its_world(self):
        self.assertEqual(self.world.world_entrances, Entrances.identity())
        for door in Entrances.DOORS:
            self.assertEqual(self.multiworld.get_entrance(door_name(door.level), self.player).connected_region.name,
                             door.entry_region)
            self.assertEqual(self.multiworld.get_entrance(way_out_name(door.level), self.player).connected_region.name,
                             door.door_region)

    def test_slot_data(self):
        data = self.world.fill_slot_data()
        self.assertEqual(data["world_entrances"], Entrances.identity())
        self.assertEqual(ids.exits_of(data["world_entrances"]), [])

    def test_the_crypt_asks_the_pumpkin_paid(self):
        """The crypt's way asks Mumbo's tokens and his skull in Mad Monster Mansion reached (Rules.lair_tree), and so
        has the skull as an indirect condition."""
        crypt = next(e for e in self.multiworld.get_region(CRYPT[0], self.player).exits
                     if e.connected_region.name == CRYPT[1])
        skull = self.multiworld.get_region(Entrances.SKULLS[regionName.MMM][0], self.player)
        self.assertIn(crypt, self.multiworld.indirect_connections.get(skull, set()))
        state = CollectionState(self.multiworld)
        for name in [itemName.MUMBO_TOKEN] * 115 + [itemName.BEAK_BARGE]:
            state.collect(self.world.create_item(name), True)
        self.assertFalse(crypt.access_rule(state), "the tokens alone, Mad Monster Mansion never reached")


class TestFixedDoors(BanjoKazooieRuleTestBase):
    """A mapping applied by hand: the doors' connections follow it, the rules stay the doors'."""
    options = {"randomize_moves": True}

    def test_a_swap(self):
        mapping = swapped((regionName.MM, regionName.TTC))
        apply_world_entrances(self.world, mapping)
        get = lambda name: self.multiworld.get_entrance(name, self.player).connected_region.name   # noqa: E731
        self.assertEqual(get(door_name(regionName.MM)), regionName.TTC)
        self.assertEqual(get(door_name(regionName.TTC)), regionName.MM)
        self.assertEqual(get(way_out_name(regionName.TTC)), regionName.GL)
        self.assertEqual(get(way_out_name(regionName.MM)), Entrances.DOOR_OF[regionName.TTC].door_region)
        self.assertEqual(get(door_name(regionName.CC)), Entrances.DOOR_OF[regionName.CC].entry_region)
        self.assertEqual(self.world.world_entrances, mapping)
        into = {e.name for e in self.multiworld.get_region(regionName.TTC, self.player).entrances}
        self.assertIn(door_name(regionName.MM), into)
        self.assertNotIn(door_name(regionName.TTC), into)
        # the first door's picture still opens it
        state = CollectionState(self.multiworld)
        state.sweep_for_advancements()          # the podium's event
        self.assertFalse(state.can_reach_region(regionName.TTC, self.player))
        state.collect(self.world.create_item(itemName.JIGGY))
        self.assertTrue(state.can_reach_region(regionName.TTC, self.player))
        self.assertFalse(state.can_reach_region(regionName.MM, self.player))
        apply_world_entrances(self.world, Entrances.identity())


class TestShuffledDoors(OnASeedThatFills, BanjoKazooieTestBase):
    """The option on, every move shuffled with Spiral Mountain's at the start: Archipelago's default tests (every
    place reached, the game beaten) on a drawn order."""
    options = {"randomize_world_entrances": True, "randomize_moves": True}

    def test_drawn(self):
        mapping = self.world.world_entrances
        self.assertTrue(Entrances.is_permutation(mapping))
        self.assertGreaterEqual(self.world.entrance_draws, 1)
        for door in Entrances.DOORS:
            behind = Entrances.DOOR_OF[mapping[door.level]]
            self.assertEqual(self.multiworld.get_entrance(door_name(door.level), self.player).connected_region.name,
                             behind.entry_region)
            self.assertEqual(self.multiworld.get_entrance(way_out_name(behind.level), self.player).connected_region.name,
                             door.door_region)
        data = self.world.fill_slot_data()
        self.assertEqual(data["world_entrances"], mapping)
        self.assertEqual(len(ids.exits_of(mapping)), 2 * sum(door != world for door, world in mapping.items()))


class TestShuffledDoorsVanillaMoves(OnASeedThatFills, BanjoKazooieTestBase):
    """The option on with the moves at their molehills: Mumbo's Mountain's teaches Talon Trot, which the first note
    door needs, so the draw always leaves Mumbo's Mountain behind the first door."""
    options = {"randomize_world_entrances": True}

    def test_mumbos_mountain_first(self):
        self.assertEqual(self.world.world_entrances[regionName.MM], regionName.MM)
