"""The whole game on Lighthouse's logic: the generated data (LogicData.py, Notes.py, from tools/lighthouse_logic.py)
holds together, the world's expressions compile to what they say, the owner's overrides name real checks, and
the goal is Gruntilda beaten."""

import unittest
from collections import Counter

from BaseClasses import CollectionState

from . import BanjoKazooieRuleTestBase, BanjoKazooieTestBase
from ..Items import jinjo_table, moves_table
from ..Locations import all_location_table, lighthouse_checks, vanilla_jinjos
from ..LogicData import CONNECTIONS, EVENTS, GOAL_EVENT, LOCATIONS, REGIONS, START
from ..Names import itemName, locationName, regionName
from ..Notes import NOTES
from ..Rules import JIGGIES_FOR_GRUNTYS_DOOR, OVERRIDES, compile_rule, note_check


def nodes(tree):
    if isinstance(tree, tuple):
        yield tree
        for part in tree[1:]:
            yield from nodes(part)


def every_rule():
    yield from (rule for _f, _t, rule in CONNECTIONS)
    yield from (rule for _r, _e, rule in EVENTS)
    yield from (row[4] for row in LOCATIONS)
    yield from (row[4] for notes in NOTES.values() for row in notes)
    yield from (rule for rule, _why in OVERRIDES.values())


class TestGeneratedData(unittest.TestCase):
    def test_every_kind_the_hack_publishes(self):
        self.assertEqual(Counter(data.group for data in all_location_table.values()),
                         {"Jiggy": 100, "Mumbo Token": 115, "Honeycomb": 24, "Molehill": 20, "Note Door": 8, "Jinjo": 45,
                          "Note": 900})

    def test_hack_ids_are_unique_by_kind(self):
        for group in ("Jiggy", "Mumbo Token", "Honeycomb", "Molehill", "Note Door", "Jinjo", "Note"):
            ids = [data.hack_id for data in all_location_table.values() if data.group == group]
            self.assertEqual(len(ids), len(set(ids)), group)

    def test_every_jinjo_is_its_own_item(self):
        # one location and one item per level and colour; unshuffled, a Jinjo holds itself (Names/itemName.py)
        self.assertEqual(set(vanilla_jinjos.values()), set(jinjo_table))
        for name, jinjo in vanilla_jinjos.items():
            self.assertEqual(all_location_table[name].hack_id, itemName.JINJOS[jinjo], name)

    def test_the_jinjo_levels_are_the_worlds(self):
        levels = {level for _name, level, _map in REGIONS}
        self.assertTrue(set(itemName.JINJO_LEVELS.values()) <= levels)
        self.assertEqual(set(itemName.JINJOS_OF_LEVEL), {row[3].split(":")[0] for row in LOCATIONS if row[1] == "Jinjo"})

    def test_every_jinjo_jiggy_asks_its_five(self):
        # Lighthouse rules Bubblegloop Swamp's `true` (BubblegloopSwamp.cpp:14); the world asks the five, as for
        # every other level (tools/lighthouse_logic.py, RULE_FIXUPS)
        rules = {row[0]: row[4] for row in LOCATIONS}
        for level in itemName.JINJO_LEVELS.values():
            (name,) = [row[0] for row in LOCATIONS if row[1] == "Jiggy" and row[2] == 10 * (
                next(n for n, lv in itemName.JINJO_LEVELS.items() if lv == level)) - 9]
            self.assertIn(("jinjos", level), list(nodes(rules[name])), name)

    def test_the_cellar_barrel_and_loggo_share_a_token(self):
        # Two places, one game id: 0x3D (docs/bk-decomp-notes.md, "Mumbo tokens"); either checks it.
        (row,) = [row for row in LOCATIONS if row[1] == "Mumbo Token" and row[2] == 0x3D]
        regions = {node[1] for node in nodes(row[4]) if node[0] == "region"}
        self.assertEqual(len(regions), 2)
        self.assertTrue(all(r.startswith(regionName.MMM) for r in regions))

    def test_every_move_asked_for_is_an_item(self):
        moves = {node[1] for rule in every_rule() for node in nodes(rule) if node[0] == "move"}
        self.assertTrue(moves <= set(moves_table), moves - set(moves_table))

    def test_every_event_asked_for_is_defined(self):
        asked = {node[1] for rule in every_rule() for node in nodes(rule) if node[0] == "event"}
        self.assertTrue(asked <= {event for _r, event, _rule in EVENTS})

    def test_every_region_named_exists(self):
        regions = {name for name, _level, _map in REGIONS}
        self.assertIn(START, regions)
        named = ({f for f, _t, _r in CONNECTIONS} | {t for _f, t, _r in CONNECTIONS} | {r for r, _e, _rule in EVENTS}
                 | {row[3] for row in LOCATIONS} | {row[3] for notes in NOTES.values() for row in notes}
                 | {node[1] for rule in every_rule() for node in nodes(rule) if node[0] == "region"})
        self.assertTrue(named <= regions, named - regions)

    def test_only_doors_with_items_are_asked_for(self):
        doors = {node[1] for rule in every_rule() for node in nodes(rule) if node[0] == "door"}
        self.assertTrue(doors <= set(range(1, 9)), doors)

    def test_every_name_constant_is_a_location(self):
        names = [value for key, value in vars(locationName).items() if key.isupper() and isinstance(value, str)]
        names += locationName.NOTE_DOOR_THRESHOLDS
        for name in names:
            self.assertIn(name, all_location_table)

    def test_every_override_names_a_check(self):
        checks = (set(lighthouse_checks.values()) | {event for _r, event, _rule in EVENTS}
                  | {note_check(level, row[0]) for level, notes in NOTES.items() for row in notes})
        self.assertTrue(set(OVERRIDES) <= checks, set(OVERRIDES) - checks)

    def test_the_goal_is_in_gruntildas_arena(self):
        (region,) = [region for region, event, _rule in EVENTS if event == GOAL_EVENT]
        self.assertEqual(region, f"{regionName.GL_LEVEL}: Gruntilda Boss Arena")


class TestCompileRule(BanjoKazooieRuleTestBase):
    options = BanjoKazooieRuleTestBase.every_move_shuffled

    def holds(self, tree, *items: str, tokens: int = 0) -> bool:
        state = CollectionState(self.multiworld)
        for name in items:
            state.collect(self.get_item_by_name(name))
        for token in self.get_items_by_name(itemName.MUMBO_TOKEN)[:tokens]:
            state.collect(token)
        rule = compile_rule(self.world, tree)
        return True if rule is None else rule(state)

    def test_moves(self):
        tree = ("all", ("move", itemName.EGGS), ("any", ("move", itemName.FLAP_FLIP), ("move", itemName.TALL_JUMP)))
        self.assertFalse(self.holds(tree, itemName.EGGS))
        self.assertTrue(self.holds(tree, itemName.EGGS, itemName.TALL_JUMP))
        self.assertFalse(self.holds(tree, itemName.FLAP_FLIP))

    def test_always_and_never(self):
        self.assertIsNone(compile_rule(self.world, True))
        self.assertIsNone(compile_rule(self.world, ("any", True, ("move", itemName.EGGS))))
        self.assertFalse(self.holds(False))
        self.assertTrue(self.holds(("not", ("move", itemName.EGGS))))

    def test_tokens_add_up_mumbos_prices(self):
        self.assertFalse(self.holds(("tokens", regionName.BGS), tokens=10))
        self.assertTrue(self.holds(("tokens", regionName.BGS), tokens=15))

    def test_door_and_picture(self):
        self.assertTrue(self.holds(("door", 1), "Note Door 1"))
        self.assertFalse(self.holds(("door", 2), "Note Door 1"))
        self.assertTrue(self.holds(("picture", regionName.MM), itemName.JIGGY))
        self.assertFalse(self.holds(("picture", regionName.TTC), itemName.JIGGY))


class TestTheGoal(BanjoKazooieTestBase):
    """Moves shuffled. Gruntilda in her arena: the final room, Grunty's door and Flight, Beak Bomb and Eggs
    (Lighthouse/src/port/Rando/Logic/Regions/GruntildasLair.cpp, the final room)."""
    options = {
        "randomize_moves": True,
    }

    def beaten_with_all_but(self, missing, jiggies=None) -> bool:
        state = CollectionState(self.multiworld)
        self.collect_all_but(missing, state)
        for jiggy in self.get_items_by_name(itemName.JIGGY)[:jiggies or 0]:
            state.collect(jiggy)
        return self.multiworld.has_beaten_game(state, self.player)

    def test_everything_beats_it(self):
        self.assertTrue(self.beaten_with_all_but([]))

    def test_each_final_battle_move_is_needed(self):
        for move in (itemName.FLIGHT, itemName.BEAK_BOMB, itemName.EGGS):
            self.assertFalse(self.beaten_with_all_but([move]), move)

    def test_gruntys_door_takes_94_jiggies(self):
        self.assertFalse(self.beaten_with_all_but([itemName.JIGGY], jiggies=JIGGIES_FOR_GRUNTYS_DOOR - 1))
        self.assertTrue(self.beaten_with_all_but([itemName.JIGGY], jiggies=JIGGIES_FOR_GRUNTYS_DOOR))

    def test_the_last_door_is_needed(self):
        self.assertFalse(self.beaten_with_all_but(["Note Door 8"]))


class TestPool(BanjoKazooieTestBase):
    """Default options: moves and honeycombs in their own places."""

    def test_one_item_per_jiggy_and_token_and_the_eight_doors(self):
        pool = Counter(item.name for item in self.multiworld.itempool)
        self.assertEqual(pool[itemName.JIGGY], 100)
        self.assertEqual(pool[itemName.MUMBO_TOKEN], 115)
        for door in itemName.NOTE_DOORS:
            self.assertEqual(pool[door], 1, door)

    def test_honeycombs_in_their_places(self):
        self.assertNotIn(itemName.EMPTY_HONEYCOMB, {item.name for item in self.multiworld.itempool})
        for name, data in all_location_table.items():
            if data.group == "Honeycomb":
                location = self.world.get_location(name)
                self.assertEqual(location.item.name, itemName.EMPTY_HONEYCOMB, name)
                self.assertTrue(location.locked, name)


class TestJinjosInTheirPlaces(BanjoKazooieTestBase):
    """Default options: each Jinjo holds itself."""

    def test_jinjos_in_their_places(self):
        self.assertFalse(set(jinjo_table) & {item.name for item in self.multiworld.itempool})
        for name, jinjo in vanilla_jinjos.items():
            location = self.world.get_location(name)
            self.assertEqual(location.item.name, jinjo, name)
            self.assertTrue(location.locked, name)


class TestJinjosShuffled(BanjoKazooieTestBase):
    options = {
        "randomize_jinjos": True,
    }

    def test_forty_five_jinjos_in_the_pool(self):
        pool = Counter(item.name for item in self.multiworld.itempool)
        self.assertEqual({name: pool[name] for name in jinjo_table}, {name: 1 for name in jinjo_table})


class TestHoneycombsShuffled(BanjoKazooieTestBase):
    options = {
        "randomize_honeycombs": True,
    }

    def test_twenty_four_honeycombs_in_the_pool(self):
        pool = [item.name for item in self.multiworld.itempool]
        self.assertEqual(pool.count(itemName.EMPTY_HONEYCOMB), 24)
