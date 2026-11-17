import typing
import unittest

from BaseClasses import CollectionState, PlandoOptions
from Options import NamedRange
from test.bases import WorldTestBase


class BanjoKazooieTestBase(WorldTestBase):
    game = "Banjo-Kazooie"

    def collect_all_but(self, item_names: typing.Union[str, typing.Iterable[str]],
                        state: typing.Optional[CollectionState] = None) -> None:
        """WorldTestBase's, but the events (Lighthouse's switches, Gruntilda beaten; Regions.py) and the items
        locked in their own places (the Jinjos and the moves when they are not shuffled) come only from their
        locations, by a sweep: collecting them directly would hold every one, whatever the rules ask to reach
        them."""
        if isinstance(item_names, str):
            item_names = (item_names,)
        if not state:
            state = self.multiworld.state
        for item in self.multiworld.get_items():
            if (item.name not in item_names and item.code is not None
                    and not (item.location is not None and item.location.locked)):
                state.collect(item, True)
        state.sweep_for_advancements()


class BanjoKazooieRuleTestBase(BanjoKazooieTestBase):
    """For tests of rules with every move shuffled (start_with_spiral_mountain_moves off), so that a state holds
    only the moves a test gives it. Archipelago's default tests do not run here: with every move shuffled about one
    seed in eight fails to fill (Options.StartWithSpiralMountainMoves), which they would show as a test failing now
    and then; the classes on the default options run them."""
    every_move_shuffled = {"randomize_moves": True, "start_with_spiral_mountain_moves": False}

    @property
    def run_default_tests(self) -> bool:
        return False


def check_presets(case: unittest.TestCase, world_type) -> None:
    """Each of the world's presets (Presets.py) names options of the world and gives each a value the option takes as
    it is: what Archipelago's test/webhost/test_option_presets.py asks, which only Archipelago's whole suite runs."""
    presets = world_type.web.options_presets
    case.assertTrue(presets)
    for preset_name, preset in presets.items():
        for key, value in preset.items():
            with case.subTest(preset=preset_name, option=key):
                case.assertIn(key, world_type.options_dataclass.type_hints)
                option = world_type.options_dataclass.type_hints[key].from_any(value)
                option.verify(world_type, "Test Player", PlandoOptions(sum(PlandoOptions)))
                case.assertFalse(str(value).startswith("random"))
                if isinstance(value, str) and not isinstance(option, NamedRange):
                    case.assertEqual(option.name_lookup.get(option.value), value)   # not an alias
