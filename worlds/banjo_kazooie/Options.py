"""Options for Banjo-Kazooie (the player's yaml). Start small; add options only when the hack and client support
them."""

from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, NamedRange, PerGameCommonOptions, Range, StartInventoryPool, Toggle


class RandomizeMoves(Toggle):
    """Shuffle Bottles' moves into the item pool. Off: each molehill gives the move it teaches, as in the
    vanilla game."""
    display_name = "Randomize Moves"


class StartWithSpiralMountainMoves(DefaultOnToggle):
    """With Randomize Moves on: start with Spiral Mountain's nine moves (Climb, Swim, Feathery Flap, Flap Flip,
    Rat-a-tat Rap, Beak Barge, Roll, Claw Swipe, Tall Jump), and let their molehills hold random items; the other
    nine moves stay shuffled. Does nothing with Randomize Moves off.

    Keep this on in a small Archipelago (Banjo-Kazooie alone or with few other games): with every move shuffled,
    the start of the game reaches only 11 places, too few for the items the rest of the game needs first, and
    about one seed in eight then fails to generate. In a larger multiworld the other games' early places can take
    those items, and turning this off becomes safer."""
    display_name = "Start with Spiral Mountain's Moves"


class SkipIntro(DefaultOnToggle):
    """Start a new game in Spiral Mountain, where the intro's cutscenes end, instead of playing them."""
    display_name = "Skip the Intro"


class SkipLairCutscene(DefaultOnToggle):
    """The first time Banjo enters Gruntilda's Lair, go straight to its lobby instead of watching the cutscene of
    Gruntilda's machine room."""
    display_name = "Skip the Lair's Cutscene"


class RandomizeHoneycombs(Toggle):
    """Shuffle Empty Honeycombs into the item pool. Off: each honeycomb is where it lies, as in the vanilla game."""
    display_name = "Randomize Empty Honeycombs"


class RandomizeJinjos(Toggle):
    """Shuffle the 45 Jinjos into the item pool, one item per level and colour (a Jinjo counts only in its own
    level). Off: each Jinjo holds itself, as in the vanilla game. Either way a level's five Jinjo items make its
    Jinjo jiggy appear beside Banjo in that level."""
    display_name = "Randomize Jinjos"


class Notesanity(Toggle):
    """Make each of the 900 notes a location, and put 900 Notes in the item pool. Picking up a note is then only a
    check, and the game's note totals (the note doors' thresholds) count the Notes received. Either way every note
    picked up stays gone, saved with the game."""
    display_name = "Notesanity"


class RandomizeWorldEntrances(Toggle):
    """Shuffle which world each of the nine world doors in Gruntilda's Lair leads into. A door keeps its own picture
    and podium; leaving a world takes Banjo back out through the door he came in by. Mumbo's forms come off on the
    way into or out of a world: in the Lair, press D-pad left near the door of a world whose Mumbo has been paid for
    that form to take it again (and D-pad left there again to change back). Without Randomize Moves some orders
    cannot be played (Mumbo's Mountain's molehill teaches Talon Trot, which the first note door needs), and the
    world draws only orders whose every check can be reached.

    In a small Archipelago some seeds then fail to generate: with Banjo-Kazooie alone, about one in a hundred with
    the moves at their molehills, one in twenty-five with Randomize Moves, and one in seven with every move shuffled
    (one in twenty without this option); none of thirty Banjo-Kazooie & Tooie seeds (measured 2026-11-05).
    Generate again with another seed."""
    display_name = "Randomize World Entrances"


class LogicType(Choice):
    """Which tricks the logic may require."""
    display_name = "Logic Type"
    option_intended = 0
    option_easy_tricks = 1
    option_hard_tricks = 2
    default = 0


class TagLink(Toggle):
    """When other multiworld games tag or swap characters, Banjo swaps with them, and his own swaps tag them: in a
    world with a Mumbo form paid for, he turns into it or back (in Gruntilda's Lair a tag waits until he is in a
    world). D-pad left does the same by hand, anywhere in such a world."""
    display_name = "Tag Link"


class MaxTraps(NamedRange):
    """The most traps that take the place of filler in the pool (the Banjo-Tooie world's option). Each trap plays
    once, when it arrives: a trip, a slip, a transformation that changes nothing, a face-plant or a tip from
    Bottles. The real number is limited by the filler the pool has."""
    display_name = "Max Traps"
    range_start = 0
    range_end = 100
    default = 0
    special_range_names = {"none": 0, "light": 15, "moderate": 30, "mayhem": 70, "unlimited": 99999}


class TripTrapWeight(Range):
    """The weight of Trip Traps among the traps: Banjo is knocked back. Needs Max Traps above 0."""
    display_name = "Trip Trap Weight"
    range_start = 0
    range_end = 100
    default = 30


class SlipTrapWeight(Range):
    """The weight of Slip Traps among the traps: Banjo slides for five seconds. Needs Max Traps above 0."""
    display_name = "Slip Trap Weight"
    range_start = 0
    range_end = 100
    default = 30


class TransformTrapWeight(Range):
    """The weight of Transform Traps among the traps: Mumbo's transformation plays, and Banjo stays as he was. Needs
    Max Traps above 0."""
    display_name = "Transform Trap Weight"
    range_start = 0
    range_end = 100
    default = 30


class SquishTrapWeight(Range):
    """The weight of Squish Traps among the traps: Banjo falls flat on his face. Needs Max Traps above 0."""
    display_name = "Squish Trap Weight"
    range_start = 0
    range_end = 100
    default = 15


class TipTrapWeight(Range):
    """The weight of Tip Traps among the traps: one of Bottles' tips. Needs Max Traps above 0."""
    display_name = "Tip Trap Weight"
    range_start = 0
    range_end = 100
    default = 20


@dataclass
class BanjoKazooieOptions(PerGameCommonOptions):
    randomize_moves: RandomizeMoves
    start_with_spiral_mountain_moves: StartWithSpiralMountainMoves
    randomize_honeycombs: RandomizeHoneycombs
    randomize_jinjos: RandomizeJinjos
    notesanity: Notesanity
    skip_intro: SkipIntro
    skip_lair_cutscene: SkipLairCutscene
    randomize_world_entrances: RandomizeWorldEntrances
    logic_type: LogicType
    death_link: DeathLink
    tag_link: TagLink
    max_traps: MaxTraps
    trip_trap_weight: TripTrapWeight
    slip_trap_weight: SlipTrapWeight
    transform_trap_weight: TransformTrapWeight
    squish_trap_weight: SquishTrapWeight
    tip_trap_weight: TipTrapWeight
    start_inventory_from_pool: StartInventoryPool
