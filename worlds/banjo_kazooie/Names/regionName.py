"""Region and level name constants.

A level's name is what the logic counts by (pictures, Mumbo's prices, notes: Rules.py). The regions are
Lighthouse's, named by tools/lighthouse_logic.py: "<level>" for the one of a level that Lighthouse names after
the level, "<level>: <Lighthouse's name>" for the others (LogicData.REGIONS).
"""

MENU = "Menu"
SM = "Spiral Mountain"
GL_LEVEL = "Gruntilda's Lair"   # the level, whose picture is Grunty's door
GL = "Gruntilda's Lair: Lobby"  # the Lair's first room, the MM lobby (MAP_69_GL_MM_LOBBY)
MM = "Mumbo's Mountain"
TTC = "Treasure Trove Cove"
CC = "Clanker's Cavern"
BGS = "Bubblegloop Swamp"
FP = "Freezeezy Peak"
GV = "Gobi's Valley"
MMM = "Mad Monster Mansion"
RBB = "Rusty Bucket Bay"
CCW = "Click Clock Wood"

LEVELS = [MM, TTC, CC, BGS, FP, GV, MMM, RBB, CCW]

# A level's prefix in the names of its locations (tools/lighthouse_logic.py writes the same)
LEVEL_PREFIX = {MM: "MM", TTC: "TTC", CC: "CC", BGS: "BGS", FP: "FP", GV: "GV", MMM: "MMM", RBB: "RBB", CCW: "CCW"}
