"""Location name constants, for the locations the world's rules and tests name. Keep in sync with
LogicData.py, which tools/lighthouse_logic.py generates with every location's name (Locations.py builds the
table from it); test_lighthouse.py checks that each constant is a location. A jiggy's, token's or honeycomb's
name in parentheses follows Lighthouse's check name.
"""

# Spiral Mountain
SM_HONEYCOMB_STUMP = "SM: Empty Honeycomb (Stump)"
SM_HONEYCOMB_WATERFALL = "SM: Empty Honeycomb (Waterfall)"
SM_HONEYCOMB_UNDERWATER = "SM: Empty Honeycomb (Underwater)"
SM_HONEYCOMB_TREE = "SM: Empty Honeycomb (Tree)"
SM_HONEYCOMB_COLLIWOBBLE = "SM: Empty Honeycomb (Colliwobble)"
SM_HONEYCOMB_QUARRIES = "SM: Empty Honeycomb (Quarries)"
SM_MOLEHILL_CLIMB = "SM: Bottles (Climb)"
SM_MOLEHILL_SWIM = "SM: Bottles (Swim)"
SM_MOLEHILL_FEATHERY_FLAP = "SM: Bottles (Feathery Flap)"
SM_MOLEHILL_FLAP_FLIP = "SM: Bottles (Flap Flip)"
SM_MOLEHILL_RATATAT = "SM: Bottles (Rat-a-tat Rap)"
SM_MOLEHILL_BEAK_BARGE = "SM: Bottles (Beak Barge)"
SM_MOLEHILL_ROLL = "SM: Bottles (Roll)"
SM_MOLEHILL_CAMERA_CONTROL = "SM: Bottles (Camera Control)"
SM_MOLEHILL_CLAW_SWIPE = "SM: Bottles (Claw Swipe)"
SM_MOLEHILL_TALL_JUMP = "SM: Bottles (Tall Jump)"  # hold A to jump higher; the Tooie world's name for it

# Gruntilda's Lair
# The note total (the worlds' best note counts added up) reaching note door 1..8's cost, wherever Banjo is.
NOTE_DOOR_THRESHOLDS = [f"GL: Note Door {door} Threshold" for door in range(1, 9)]
GL_JIGGY_FIRST = "GL: Jiggy (First)"
GL_JIGGY_MM_WITCH_SWITCH = "GL: Jiggy (MM Witch Switch)"
GL_MOLEHILL_NOTE_DOORS = "GL: Bottles (Note Doors)"  # the Lair's Bottles, ability 0x13 (the client always sends it)

# Mumbo's Mountain
MM_JIGGY_JINJOS = "MM: Jiggy (Jinjos)"
MM_JINJO_BLUE = "MM: Jinjo (Blue)"
MM_JINJO_GREEN = "MM: Jinjo (Green)"   # in the 4th hut Banjo breaks (hack/bk/decomp/src/MM/ch/hut.c:53-60)
MM_JINJO_ORANGE = "MM: Jinjo (Orange)"
MM_JINJO_PINK = "MM: Jinjo (Pink)"
MM_JINJO_YELLOW = "MM: Jinjo (Yellow)"
MM_JIGGY_TICKERS_TOWER = "MM: Jiggy (Ticker's Tower)"
MM_JIGGY_MUMBOS_SKULL = "MM: Jiggy (Mumbo's Skull)"
MM_JIGGY_JUJU = "MM: Jiggy (Juju)"
MM_JIGGY_HUTS = "MM: Jiggy (Huts)"
MM_JIGGY_RUINS = "MM: Jiggy (Ruins)"
MM_JIGGY_HILL = "MM: Jiggy (Hill)"
MM_JIGGY_ORANGE_PADS = "MM: Jiggy (Orange Pads)"
MM_JIGGY_CHIMPY = "MM: Jiggy (Chimpy)"
MM_JIGGY_CONGA = "MM: Jiggy (Conga)"
MM_TOKEN_STUMP_NEAR_CONGA = "MM: Mumbo Token (Stump Near Conga)"
MM_TOKEN_BEHIND_RUINS = "MM: Mumbo Token (Behind Ruins)"
MM_TOKEN_UNDER_RAMP_TO_MUMBOS_SKULL = "MM: Mumbo Token (Under Ramp to Mumbo's Skull)"
MM_TOKEN_BEHIND_PINK_JINJO = "MM: Mumbo Token (Behind Pink Jinjo)"
MM_TOKEN_INSIDE_TICKERS_TOWER = "MM: Mumbo Token (Inside Ticker's Tower)"
MM_MOLEHILL_EGGS = "MM: Bottles (Eggs)"
MM_MOLEHILL_BEAK_BUSTER = "MM: Bottles (Beak Buster)"
MM_MOLEHILL_TALON_TROT = "MM: Bottles (Talon Trot)"

# Treasure Trove Cove
TTC_JIGGY_SANDCASTLE = "TTC: Jiggy (Sandcastle)"
