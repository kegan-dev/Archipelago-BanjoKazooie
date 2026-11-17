"""Item name constants. Keep in sync with Items.py."""

JIGGY = "Jiggy"
EMPTY_HONEYCOMB = "Empty Honeycomb"
MUMBO_TOKEN = "Mumbo Token"
NOTE = "Note"  # with notesanity: one note received (the hack's note totals count them)

# Jinjos: one item per level and colour, counting only in its own level, where the five give the level's Jinjo
# jiggy (the owner's decision of 2026-10-29; Lighthouse's model). The colours in the order of their bits in the
# game's mask of a level's Jinjos (hack/bk/decomp/include/bkbt.h, BKBT_AP_JINJO_INDEX: marker id -
# MARKER_5A_JINJO_BLUE), the levels by enum level_e (hack/bk/decomp/include/enums.h) with their names
# (Names/regionName.py). A Jinjo's hack id, the index the hack publishes and reads it under, is
# (level - 1) * 5 + colour (Names/ids.py, jinjo_item_id and jinjo_location_id).
JINJO_COLOURS = ("Blue", "Green", "Orange", "Pink", "Yellow")
JINJO_LEVELS = {1: "Mumbo's Mountain", 2: "Treasure Trove Cove", 3: "Clanker's Cavern", 4: "Bubblegloop Swamp",
                5: "Freezeezy Peak", 7: "Gobi's Valley", 8: "Click Clock Wood", 9: "Rusty Bucket Bay",
                10: "Mad Monster Mansion"}


def jinjo_item_name(colour: str, level_name: str) -> str:
    """A Jinjo's item, e.g. "Blue Jinjo (Mumbo's Mountain)" (tools/lighthouse_logic.py writes the same)."""
    return f"{colour} Jinjo ({level_name})"


# name -> hack id, and a level's name -> its five names
JINJOS = {jinjo_item_name(colour, name): (level - 1) * 5 + bit
          for level, name in JINJO_LEVELS.items() for bit, colour in enumerate(JINJO_COLOURS)}
JINJOS_OF_LEVEL = {name: tuple(jinjo_item_name(colour, name) for colour in JINJO_COLOURS) for name in JINJO_LEVELS.values()}

# Moves taught by Bottles (BK_Randomizer/Randomization_Processes/Dicts_And_Lists/Warps.py:751-764)
EGGS = "Eggs"
TALON_TROT = "Talon Trot"
BEAK_BUSTER = "Beak Buster"
SHOCK_JUMP = "Shock Spring Jump"
FLIGHT = "Flight"
WONDERWING = "Wonderwing"
WADING_BOOTS = "Wading Boots"
BEAK_BOMB = "Beak Bomb"
TURBO_TROT = "Turbo Talon Trot"
# Spiral Mountain tutorial moves
CLIMB = "Climb"
SWIM = "Swim"
FEATHERY_FLAP = "Feathery Flap"
FLAP_FLIP = "Flap Flip"
RATATAT_RAP = "Rat-a-tat Rap"
BEAK_BARGE = "Beak Barge"
ROLL = "Roll"
CLAW_SWIPE = "Claw Swipe"
TALL_JUMP = "Tall Jump"  # hold A to jump higher; the Tooie world's name for it
# Camera control is not an item: the client always sends it (CLAUDE.md, "BK's Archipelago items").

# Note doors 1..8 by number, 1 being the 50-note door (Names/ids.py): an item opens its door when Banjo
# next comes near it (hack/bk/decomp/BKBT.md, "Note doors as Archipelago items and locations"). Named by
# number, not by cost, so that the names stay right if the costs become settings.
NOTE_DOORS = [f"Note Door {door}" for door in range(1, 9)]

# Filler
EXTRA_LIFE = "Extra Life"
BLUE_EGG_REFILL = "Blue Egg Refill"
RED_FEATHER_REFILL = "Red Feather Refill"
GOLD_FEATHER_REFILL = "Gold Feather Refill"

# Traps, the Banjo-Tooie world's five under the same names, in the order of the hack's kinds (hack/bk/decomp/
# include/bkbt.h, BKBT_AP_TRAP_TRIP..TIP, which are Tooie's): only the solo world has them; the combined world gives
# Tooie's, which play in either game
TRIP_TRAP = "Trip Trap"
SLIP_TRAP = "Slip Trap"
TRANSFORM_TRAP = "Transform Trap"
SQUISH_TRAP = "Squish Trap"
TIP_TRAP = "Tip Trap"
TRAPS = (TRIP_TRAP, SLIP_TRAP, TRANSFORM_TRAP, SQUISH_TRAP, TIP_TRAP)
