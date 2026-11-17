"""Access rules for Banjo-Kazooie.

The rules are Lighthouse's (the Lighthouse/ submodule, HarbourMasters' PC port, whose randomizer has a rule for
every check of the game with every move shuffled; docs/upstream-lighthouse.md), generated into LogicData.py and
Notes.py by tools/lighthouse_logic.py as small expressions, which compile_rule turns into Archipelago rules. The
world's own decisions sit on top, here:

- the owner's tries beat Lighthouse's rule (OVERRIDES, the owner's choice of 2026-10-28: "Lighthouse except your
  tries");
- a picture takes the jiggies of the pictures before it too, and a transformation the prices of the earlier
  transformations, because the hack spends held jiggies and tokens (JIGGIES_TO_OPEN, TOKENS_TO_TRANSFORM;
  Lighthouse asks one price);
- a note door opens on its item and the door's place reached, not on notes (the hack's design), and its threshold
  is a location the notes in logic reach (notes_in_logic);
- a Mumbo form the Lair asks for comes from quick transform at its world's door, once Mumbo was paid for it
  (lair_tree), not from a form carried out of the world, which the hack takes off at the way out.
"""

from collections import Counter
from itertools import accumulate
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from BaseClasses import CollectionState
from worlds.generic.Rules import set_rule

from .Entrances import DOOR_OF, SKULLS
from .Locations import (NOTE_DOOR_COSTS, lighthouse_checks, lighthouse_rules, lighthouse_table, note_check, note_checks,
                        note_rules)
from .LogicData import EVENTS, GOAL_EVENT, REGIONS
from .Names import itemName, locationName, regionName
from .Notes import NOTES

if TYPE_CHECKING:
    from . import BanjoKazooieWorld

Rule = Callable[[CollectionState], bool]

# -- World entry ---------------------------------------------------------------------------------------

# The Lair's pictures in the order its rooms reach them, with the jiggies each takes: PICTURE_INFO,
# hack/bk/decomp/src/lair/jigsawpicture.c:40-52; the hack keeps these costs (hack/bk/decomp/BKBT.md,
# "Jiggies as Archipelago items and locations"). A piece placed spends a held jiggy, and a finished
# picture keeps its pieces: the podium does not take Banjo on again (`!isPictureComplete`,
# jigsawpicture.c:574), so C-down cannot give them back. The hack gives the held jiggies from the
# client's total of jiggies received, so opening the nth world takes the costs of the first n received.
PICTURE_COSTS: List[Tuple[str, int]] = [
    (regionName.MM, 1),
    (regionName.TTC, 2),
    (regionName.CC, 5),
    (regionName.BGS, 7),
    (regionName.FP, 8),
    (regionName.GV, 9),
    (regionName.MMM, 10),
    (regionName.RBB, 12),
    (regionName.CCW, 15),
]
GRUNTYS_DOOR_COST = 25  # PICTURE_INFO[9], the door to the final battle
# PICTURE_INFO[10], double health (4), is optional: the logic never counts on it, nor on the sandcastle's
# cheats, which fill CC's to CCW's pictures without spending (hack/bk/decomp/src/TTC/ma/castle.c:954-1016).

JIGGIES_TO_OPEN: Dict[str, int] = dict(zip(
    [level for level, _ in PICTURE_COSTS], accumulate(cost for _, cost in PICTURE_COSTS)))
JIGGIES_FOR_GRUNTYS_DOOR = JIGGIES_TO_OPEN[regionName.CCW] + GRUNTYS_DOOR_COST
# Lighthouse's CAN_UNLOCK_WORLD(LEVEL_6_LAIR) is Grunty's door (Lighthouse/src/port/Rando/Logic/Logic.h, CanOpenWorld).
PICTURE_JIGGIES: Dict[str, int] = {**JIGGIES_TO_OPEN, regionName.GL_LEVEL: JIGGIES_FOR_GRUNTYS_DOOR}

# -- Transformations -----------------------------------------------------------------------------------

# Mumbo's prices, in the order the Lair opens the worlds whose skulls charge them: __transformation_getCost,
# hack/bk/decomp/src/core2/ch/mumbo.c:77-91; a skull's transformation is the one whose pad is in its map
# (func_802D16AC, :54-71). The hack keeps these prices (the owner's decision of 2026-10-27,
# docs/tutorials/12-tokens.md). Mumbo charges the held tokens (:353), and only until the transformation's
# FILEPROG_90..94 flag says it was paid (:93-95, :320): the spell sets it (:395) and the game saves it. In
# the skulls after Mumbo's Mountain's, B now and then starts a T-rex joke or a mistake instead (:326-346);
# each charges the same price once from its text callback (:161-167, :171-179) and then transforms Banjo
# and sets the flag, so neither costs more. Mumbo in the Lair's crypt charges nothing (:320).
TRANSFORMATION_COSTS: List[Tuple[str, int]] = [
    (regionName.MM, 5),    # termite
    (regionName.BGS, 10),  # crocodile
    (regionName.FP, 15),   # walrus
    (regionName.MMM, 20),  # pumpkin
    (regionName.CCW, 25),  # bee
]

# The rule: a transformation needs its price and the prices of the transformations before it, added up,
# in Mumbo tokens received (5, 15, 30, 50, 75). The hack gives the held tokens from the client's total of
# tokens received and Mumbo spends them (hack/bk/decomp/BKBT.md, "Mumbo tokens as Archipelago items and
# locations"), so what one transformation needs depends on which were bought before it. The worlds open in
# the Lair's order (World entry above), so whenever the logic has a transformation it has every earlier
# one too. A player who buys each transformation only once the logic has it then always holds enough: the
# ones bought so far and this one cost at most the cumulative price of the latest of them, and the logic
# asked for that many received before allowing it. Buying a later one first, out of logic (the walrus with
# 20 tokens received, before the crocodile), can leave the player short for an earlier one until more
# tokens come; no rule that only grows with the items received can rule that out without asking for all 75
# from the first transformation on. Lighthouse asks the transformation's own price
# (Lighthouse/src/port/Rando/Logic/Logic.h, CanUseTransformation).
TOKENS_TO_TRANSFORM: Dict[str, int] = dict(zip(
    [level for level, _ in TRANSFORMATION_COSTS], accumulate(cost for _, cost in TRANSFORMATION_COSTS)))


def transformation_rule(world: "BanjoKazooieWorld", level: str) -> Rule:
    """Whether Mumbo in `level` can transform Banjo: TOKENS_TO_TRANSFORM[level] tokens received. Reaching
    his skull is the region's part."""
    count, player, token = TOKENS_TO_TRANSFORM[level], world.player, world.bk_item(itemName.MUMBO_TOKEN)
    return lambda state: state.has(token, player, count)


# The Lair's forms. In retail Banjo carries a Mumbo form out of its world into the world's own lobby, where the
# Lair's barriers keep it, and Lighthouse's rules for the Lair's checks that need one (two witch-switch jiggies, a
# podium, the crypt and a token) ask only the form's tokens. The hack takes every form off on the way between the
# Lair and a world, so that none goes through a door the exit map changed or comes out into another lobby
# (hack/bk/decomp/BKBT.md, "The exit map and the quick transform"), and gives it back at the world's door instead:
# D-pad left there, once Mumbo was paid for the form (quick transform). So in a rule of a Lair region a form asks
# its tokens, a region of its Mumbo's skull reached (where he is paid), and its world's door reached, unless the
# rule's region is that door's own (Entrances.DOOR_OF, SKULLS). Whatever door leads into the world: the form comes
# at its own door. The token above the 640 door's water is the one rule whose region is not the form's door's
# (Lighthouse's bee flies there from the Click Clock Wood lobby). test/test_entrances.py pins the five rules.

_LEVEL_OF_REGION: Dict[str, str] = {name: level for name, level, _map in REGIONS}


def lair_tree(tree, region: Optional[str]):
    """A rule's expression as the world holds it to, for a rule of `region` (a location's, an event's or the source
    of a connection): in a region of the Lair, each ('tokens', level) with the skull and the door it needs."""
    if _LEVEL_OF_REGION.get(region) != regionName.GL_LEVEL:
        return tree
    return _lair_forms(tree, region)


def _lair_forms(tree, region: str):
    if not isinstance(tree, tuple):
        return tree
    if tree[0] == "tokens":
        level = tree[1]
        parts = [tree, ("any", *(("region", skull) for skull in SKULLS[level]))]
        if DOOR_OF[level].door_region != region:
            parts.append(("region", DOOR_OF[level].door_region))
        return ("all", *parts)
    if tree[0] in ("all", "any", "not"):
        return (tree[0], *(_lair_forms(part, region) for part in tree[1:]))
    return tree


def region_terms(tree) -> List[str]:
    """The regions an expression asks to be reached: an entrance whose rule asks one needs an indirect condition."""
    if not isinstance(tree, tuple):
        return []
    if tree[0] == "region":
        return [tree[1]]
    if tree[0] in ("all", "any", "not"):
        return [region for part in tree[1:] for region in region_terms(part)]
    return []


# -- Lighthouse's expressions --------------------------------------------------------------------------

# A world that holds BK's regions answers three questions, which BanjoKazooieWorld answers with the names
# themselves and the combined world (worlds/banjo_kazooie_tooie) with its own: bk_item(name), the item a BK item
# is in that world; bk_region(name), the region a BK region is (None: left out); bk_move(move), the item that
# teaches a BK move, or a rule for it.


def move_rule(world: "BanjoKazooieWorld", move: str) -> Rule:
    """The rule of a BK move: the world's item for it, or its rule."""
    target, p = world.bk_move(move), world.player
    if callable(target):
        return target
    return lambda state: state.has(target, p)


def compile_rule(world: "BanjoKazooieWorld", tree) -> Optional[Rule]:
    """An Archipelago rule from an expression of tools/lighthouse_logic.py; None for one that always holds."""
    p = world.player
    if tree is True:
        return None
    if tree is False:
        return lambda state: False
    kind = tree[0]
    if kind == "move":
        return move_rule(world, tree[1])
    if kind == "event":
        event = tree[1]
        return lambda state: state.has(event, p)
    if kind == "tokens":
        return transformation_rule(world, tree[1])
    if kind == "picture":
        count, jiggy = PICTURE_JIGGIES[tree[1]], world.bk_item(itemName.JIGGY)
        return lambda state: state.has(jiggy, p, count)
    if kind == "door":
        item = world.bk_item(itemName.NOTE_DOORS[tree[1] - 1])
        return lambda state: state.has(item, p)
    if kind == "jinjos":
        items = [world.bk_item(jinjo) for jinjo in itemName.JINJOS_OF_LEVEL[tree[1]]]
        return lambda state: state.has_all(items, p)
    if kind == "region":
        region = world.bk_region(tree[1])
        if region is None:
            return lambda state: False
        return lambda state: state.can_reach_region(region, p)
    if kind == "not":
        inner = compile_rule(world, tree[1]) or (lambda state: True)
        return lambda state: not inner(state)
    if kind in ("all", "any"):
        targets = [world.bk_move(part[1]) for part in tree[1:] if isinstance(part, tuple) and part[0] == "move"]
        if len(targets) == len(tree) - 1 and not any(callable(target) for target in targets):   # the common case
            items = tuple(targets)
            if kind == "all":
                return lambda state: state.has_all(items, p)
            return lambda state: state.has_any(items, p)
        parts = [compile_rule(world, part) for part in tree[1:]]
        if kind == "any" and None in parts:
            return None
        parts = [part for part in parts if part is not None]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        if kind == "all":
            return lambda state: all(part(state) for part in parts)
        return lambda state: any(part(state) for part in parts)
    raise ValueError(f"unknown expression {tree!r}")


# -- The owner's tries ---------------------------------------------------------------------------------

_HIGHER_JUMP = ("any", ("move", itemName.TALL_JUMP), ("move", itemName.FLAP_FLIP))
_HUT_BREAK = ("all", ("move", itemName.BEAK_BUSTER), _HIGHER_JUMP)

# Lighthouse check -> (the rule the owner's hand tests found, which replaces Lighthouse's; where it comes from).
OVERRIDES: Dict[str, Tuple[object, str]] = {
    # Lighthouse: Flap Flip, Talon Trot or the termite (MumbosMountain.cpp:136).
    "RC_MM_MUMBO_TOKEN_INSIDE_TICKERS_TOWER": (
        ("any", ("move", itemName.TALL_JUMP), ("move", itemName.FLAP_FLIP), ("move", itemName.FEATHERY_FLAP),
         ("move", itemName.RATATAT_RAP)),
        "2026-10-27/28: a plain jump does not reach it; Feathery Flap alone and the Rat-a-tat Rap alone do, and "
        "Tall Jump and Flap Flip are the owner's sure judgement; Beak Buster untried"),
    # A hut breaks only to a Beak Buster from at least 150 above its base (hack/bk/decomp/src/MM/ch/hut.c:81-82),
    # from its roof, which a plain jump does not reach. Lighthouse: the Beak Buster alone (MumbosMountain.cpp:15,
    # :22, :118-122).
    "RC_MM_JIGGY_HUTS": (_HUT_BREAK, "2026-10-28: the huts broken with the Beak Buster and Tall Jump or Flap Flip"),
    "RC_MM_JINJO_GREEN": (_HUT_BREAK, "2026-10-28: the green Jinjo is in a hut (hut.c:53-61), as the huts"),
    **{f"RC_MM_NOTE_HUT_BUNDLE_{n}": (_HUT_BREAK, "2026-10-28: the first hut's five notes, as the huts")
       for n in range(1, 6)},
    # Lighthouse: nothing (MumbosMountain.cpp:112-117).
    **{f"RC_MM_NOTE_HUT_ROOF_{n}": (("any", _HIGHER_JUMP, ("tokens", regionName.MM)),
                                    "2026-10-28: the huts' roofs with Tall Jump or Flap Flip, or as the termite")
       for n in range(1, 7)},
    # Lighthouse: the eggs alone (MumbosMountain.cpp:17).
    "RC_MM_JIGGY_JUJU": (("all", ("move", itemName.EGGS), _HIGHER_JUMP),
                         "2026-10-28, the owner's report: Eggs and Flap Flip or Tall Jump"),
    # The letters on the Sandcastle's floor take a Beak Buster only while LEVEL_FLAG_2 is set
    # (hack/bk/decomp/src/TTC/ma/castle.c:618), which only Leaky sets, at the second egg into the bucket
    # (src/TTC/ch/leaky.c:108-120). Lighthouse: the Beak Buster alone (TreasureTroveCove.cpp:141), though Dive
    # alone gets Banjo inside (:112) with the water still up.
    "RC_TTC_JIGGY_SANDCASTLE": (("all", ("move", itemName.BEAK_BUSTER), ("event", "RA_DRAIN_WATER_SANDCASTLE")),
                                "2026-10-29, the owner's report, and the code: Eggs to drain the water"),
}


def rule_of(check: Optional[str], lighthouse_rule):
    """The expression a check is held to: the owner's, or else Lighthouse's."""
    return OVERRIDES[check][0] if check in OVERRIDES else lighthouse_rule


# -- Notes and the note doors' thresholds -------------------------------------------------------------

# A note door's threshold is checked once the note total reaches the door's cost (Locations.NOTE_DOOR_table).
# The hack keeps every note picked up, so a level's count is every note picked up there: the logic counts every
# note the items in hand reach, and the levels add up. With notesanity the total is the Notes received instead.

# The notes the world counts with every item: all of Notes.NOTES. A threshold is a location only when its cost
# is within them (__init__.py, location_enabled).
NOTES_IN_WORLD = sum(len(notes) for notes in NOTES.values())

# (region, the notes there that ask nothing more, [(count, rule)] for the others)
NoteGroup = Tuple[str, int, List[Tuple[int, Rule]]]


def note_groups(world: "BanjoKazooieWorld") -> List[NoteGroup]:
    """The notes by region, those that ask nothing but the region counted apart from those with a rule (which
    share one compiled rule per expression)."""
    keys = Counter((region, rule_of(note_check(level, name), rule))
                   for level, notes in NOTES.items() for name, _map, _pos, region, rule, _n, _loc in notes)
    by_region: Dict[str, Tuple[int, List[Tuple[int, Rule]]]] = {}
    for (bk_region, tree), count in keys.items():
        region = world.bk_region(bk_region)
        if region is None:      # a region the world leaves out: its notes are not counted
            continue
        free, ruled = by_region.get(region, (0, []))
        rule = compile_rule(world, tree)
        if rule is None:
            free += count
        else:
            ruled.append((count, rule))
        by_region[region] = (free, ruled)
    # the regions with the most notes first, so that a threshold is often settled early
    return sorted(((region, free, ruled) for region, (free, ruled) in by_region.items()),
                  key=lambda group: -(group[1] + sum(count for count, _rule in group[2])))


def notes_in_logic(world: "BanjoKazooieWorld", state: CollectionState, enough: Optional[int] = None) -> int:
    """The notes `state` reaches: in every region it reaches, those whose rule it meets. With `enough`, it may
    stop counting once it has that many."""
    total, player = 0, world.player
    for region, free, ruled in world.note_groups:
        if not state.can_reach_region(region, player):
            continue
        total += free + sum(count for count, rule in ruled if rule(state))
        if enough is not None and total >= enough:
            break
    return total


def note_door_threshold(world: "BanjoKazooieWorld", door: int) -> Rule:
    """The rule of note door number `door`'s threshold: the notes in logic reach its cost. A location's rule
    may ask whether a region is reached; only an entrance's would need an indirect condition."""
    cost = NOTE_DOOR_COSTS[door - 1]
    if world.options.notesanity:
        # the hack's note totals are the Notes received (hack/bk/decomp/BKBT.md, "Notes kept, and notes as
        # Archipelago locations")
        p, note = world.player, world.bk_item(itemName.NOTE)
        return lambda state: state.has(note, p, cost)
    return lambda state: notes_in_logic(world, state, cost) >= cost


# -- Setting them ---------------------------------------------------------------------------------------


def event_location_name(region: str, event: str) -> str:
    return f"{event} ({region})"


def set_rules(world: "BanjoKazooieWorld") -> None:
    set_location_rules(world)
    p = world.player
    world.multiworld.completion_condition[p] = lambda state: state.has(GOAL_EVENT, p)


def set_location_rules(world: "BanjoKazooieWorld") -> None:
    """Every rule but the goal's: the combined world sets its own goal."""
    world.note_groups = note_groups(world)
    for name in world.enabled_location_names:
        if name in lighthouse_rules:
            rule = compile_rule(world, lair_tree(rule_of(lighthouse_checks[name], lighthouse_rules[name]),
                                                 lighthouse_table[name].region))
            if rule is not None:
                set_rule(world.get_location(name), rule)
        elif name in note_rules:     # with notesanity
            rule = compile_rule(world, rule_of(note_checks[name], note_rules[name]))
            if rule is not None:
                set_rule(world.get_location(name), rule)
    for door, name in enumerate(locationName.NOTE_DOOR_THRESHOLDS, start=1):
        if name in world.enabled_location_names:
            set_rule(world.get_location(name), note_door_threshold(world, door))
    for region, event, tree in EVENTS:
        if world.bk_region(region) is None:
            continue
        rule = compile_rule(world, lair_tree(rule_of(event, tree), region))
        if rule is not None:
            set_rule(world.get_location(event_location_name(region, event)), rule)
