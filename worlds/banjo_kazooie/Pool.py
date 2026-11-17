"""The item pool of Banjo-Kazooie's part: the BK world's whole pool, and the combined world's BK half
(worlds/banjo_kazooie_tooie).

create_pool(world) places the locked items, precollects and returns the rest; the world pads it with filler.
It asks the world for every item by its BK name (world.create_item) and leaves the moves to world.bk_place_moves,
which the BK world answers with place_molehill_moves and the combined world with its shared moves.
"""

from typing import TYPE_CHECKING, List

from BaseClasses import Item, ItemClassification

from .Items import SM_TUTORIAL_MOVES
from .Locations import NOTE_DOOR_COSTS, all_location_table, vanilla_jinjos, vanilla_molehill_moves
from .Names import itemName
from .Rules import JIGGIES_FOR_GRUNTYS_DOOR, TOKENS_TO_TRANSFORM

if TYPE_CHECKING:
    from . import BanjoKazooieWorld


def place_molehill_moves(world: "BanjoKazooieWorld", pool: List[Item]) -> None:
    """The BK world's moves: shuffled into the pool, or each at the molehill that teaches it."""
    if world.options.randomize_moves:
        moves = list(vanilla_molehill_moves.values())
        if world.options.start_with_spiral_mountain_moves:
            # Spiral Mountain's nine from the start, their molehills holding random items: the start then
            # reaches enough places for the fill (Options.StartWithSpiralMountainMoves).
            for move in SM_TUTORIAL_MOVES:
                moves.remove(move)
                world.multiworld.push_precollected(world.create_item(move))
        pool.extend(world.create_item(move) for move in moves)
    else:
        # As in the vanilla game, each molehill gives the move it teaches.
        for loc_name, move in vanilla_molehill_moves.items():
            world.get_location(loc_name).place_locked_item(world.create_item(move))


def create_pool(world: "BanjoKazooieWorld") -> List[Item]:
    """The pool: the moves of the molehills, one jiggy per jiggy location, one Mumbo token per token location,
    one empty honeycomb per honeycomb location, the eight note doors (each opens a part of the Lair the world
    has), the 45 Jinjos and, with notesanity, a Note per note (Notes.py). The locations counted are the world's
    enabled ones."""
    pool: List[Item] = []
    world.bk_place_moves(pool)
    # Jiggies and tokens beyond the most a rule asks (Grunty's door's 94, all of Mumbo's prices' 75) are
    # useful, not progression: the client gives every one received, and the logic counts only the
    # progression ones (a state collects only progression items), so the fill has fewer to place.
    for group, item_name, needed in (("Jiggy", itemName.JIGGY, JIGGIES_FOR_GRUNTYS_DOOR),
                                     ("Mumbo Token", itemName.MUMBO_TOKEN, max(TOKENS_TO_TRANSFORM.values()))):
        count = sum(all_location_table[name].group == group for name in world.enabled_location_names)
        pool.extend(world.create_item(item_name) for _ in range(min(count, needed)))
        pool.extend(world.create_item(item_name, ItemClassification.useful) for _ in range(count - needed))
    honeycombs = [name for name in world.enabled_location_names if all_location_table[name].group == "Honeycomb"]
    if world.options.randomize_honeycombs:
        pool.extend(world.create_item(itemName.EMPTY_HONEYCOMB) for _ in honeycombs)
    else:
        # As in the vanilla game, each honeycomb is where it lies.
        for loc_name in honeycombs:
            world.get_location(loc_name).place_locked_item(world.create_item(itemName.EMPTY_HONEYCOMB))
    pool.extend(world.create_item(door) for door in itemName.NOTE_DOORS)
    if world.options.notesanity:
        # One Note per note location; beyond the most a threshold asks (door 8's 810) they are useful, as the
        # jiggies and tokens above.
        count = sum(all_location_table[name].group == "Note" for name in world.enabled_location_names)
        needed = max(NOTE_DOOR_COSTS)
        pool.extend(world.create_item(itemName.NOTE) for _ in range(min(count, needed)))
        pool.extend(world.create_item(itemName.NOTE, ItemClassification.useful) for _ in range(count - needed))
    jinjos = {name: jinjo for name, jinjo in vanilla_jinjos.items() if name in world.enabled_location_names}
    if world.options.randomize_jinjos:
        pool.extend(world.create_item(jinjo) for jinjo in jinjos.values())
    else:
        # As in the vanilla game, each Jinjo is where it is (and its item, received, counts in its level).
        for loc_name, jinjo in jinjos.items():
            world.get_location(loc_name).place_locked_item(world.create_item(jinjo))
    return pool
