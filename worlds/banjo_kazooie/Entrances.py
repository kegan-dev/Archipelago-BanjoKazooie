"""Banjo-Kazooie's nine world entrances in Gruntilda's Lair, their ways out, and the exit map that shuffles them.

Each world has one door in the Lair and one way out (the fork's hack/bk/decomp/BKBT.md, "The exit map and the quick
transform"): the door's warp in its lobby asks for the world's main map at its entrance (the `warp_*EnterLevel`
functions, src/core2/code_956B0.c), and the world's exit pad (actor 0x2E4, one in each world's main map) asks for
the lobby, by the door, from the game's table of ways out (D_8036C560, src/core2/gc/pauseMenu.c:102-114;
gcpausemenu_returnToLair, :1537-1544). A shuffle is a mapping door -> world, every world behind one door: door d's
warp then leads into world w, and w's way out back to door d, where Banjo went in (docs/ROADMAP.md, "The finished
game": leave by the entrance you came in). The hack's exit map does it (include/bkbt.h, BkbtApExit): two entries for
each door that does not lead to its own world, written by the client (client/hack.py, client/ids.py exits_of).

In the logic (LogicData.CONNECTIONS, generated from Lighthouse) each door is one entry edge, door_region ->
entry_region, with the door's own rule (its picture's jiggies and its podium reached), and one exit edge back,
entry_region -> door_region, True. Regions.connect_regions keeps the door's rule on its edge and points the edge at
the world behind it.

Pure (only the world's names), so that client/ids.py, which a tool loads with the client (tools/bk_client_check.py),
and the tools can use it.
"""

from typing import Dict, List, Mapping, NamedTuple, Tuple

from .Names import regionName


class WorldDoor(NamedTuple):
    level: str                  # the world, by its level name (Names/regionName.py)
    door_region: str            # the Lair region of its door: the entry edge's source in LogicData.CONNECTIONS
    entry_region: str           # the world's first region: the entry edge's target
    lobby: int                  # the Lair map of the door (enum map_e)
    entrance: Tuple[int, int]   # (map, exit) the door's warp asks for: the world's main map at its entrance
    way_out: Tuple[int, int]    # (map, exit) the world's exit pad asks for: the lobby, at the door


_GL = "Gruntilda's Lair: "
# The Lair's order. The warps: hack/bk/decomp/src/core2/code_956B0.c (line of the function); the ways out:
# D_8036C560 (src/core2/gc/pauseMenu.c:103-112); the maps and exits by name in include/enums.h. Each lobby holds its
# door's warp node and no other world's (a read-only scan of the retail ROM's setups, 2026-11-05), and each world's
# main map one exit pad, under its entrance's marker (the scan of 2026-11-05).
DOORS: Tuple[WorldDoor, ...] = (
    WorldDoor(regionName.MM, regionName.GL, regionName.MM,
              0x69, (0x02, 0x05), (0x69, 0x02)),                    # warp_mmEnterLevel :622
    WorldDoor(regionName.TTC, _GL + "Near Treasure Trove Cove Entrance", regionName.TTC,
              0x6D, (0x07, 0x04), (0x6D, 0x04)),                    # warp_ttcEnterLevel :935
    WorldDoor(regionName.CC, _GL + "Near Clanker's Cavern Entrance", "Clanker's Cavern: Clanker's Cavern Entrance",
              0x70, (0x0B, 0x05), (0x70, 0x02)),                    # warp_ccEnterLevel :939
    WorldDoor(regionName.BGS, _GL + "Near Bubblegloop Swamp Entrance", regionName.BGS,
              0x72, (0x0D, 0x02), (0x72, 0x02)),                    # warp_bgsEnterLevel :943
    WorldDoor(regionName.FP, _GL + "Near Freezeezy Peak Entrance", "Freezeezy Peak: Freezeezy Peak Entrance",
              0x6F, (0x27, 0x01), (0x6F, 0x06)),                    # warp_fpEnterLevel :1176
    WorldDoor(regionName.GV, _GL + "Near Gobi's Valley Entrance", regionName.GV,
              0x6E, (0x12, 0x08), (0x6E, 0x03)),                    # warp_gvEnterLevel :947
    WorldDoor(regionName.MMM, _GL + "Near Mad Monster Mansion Entrance", regionName.MMM,
              0x75, (0x1B, 0x14), (0x75, 0x02)),                    # warp_mmmEnterLevel :951
    WorldDoor(regionName.RBB, _GL + "Near Rusty Bucket Bay Entrance", regionName.RBB,
              0x77, (0x31, 0x10), (0x77, 0x02)),                    # warp_rbbEnterLevel :955
    WorldDoor(regionName.CCW, _GL + "Near Click Clock Wood Entrance", "Click Clock Wood: Click Clock Wood Entrance",
              0x79, (0x40, 0x07), (0x79, 0x06)),                    # warp_ccwEnterLevel :1389
)
DOOR_OF: Dict[str, WorldDoor] = {door.level: door for door in DOORS}
LEVELS: Tuple[str, ...] = tuple(door.level for door in DOORS)

# The Lair's forms: the worlds whose Mumbo the Lair needs a form of, with the regions of that Mumbo's skull (a
# region of the list reached and his price is a form paid for). In the Lair a form comes from quick transform at the
# world's own door (the hack's bkbt_quickTransform), whatever door leads into the world (Rules.lair_tree). Click
# Clock Wood's Winter skull is left out of the regions (tools/lighthouse_logic.py's fixes), and its other three
# are each a way to the bee.
SKULLS: Dict[str, Tuple[str, ...]] = {
    regionName.MM: ("Mumbo's Mountain: Inside Mumbo's Skull",),
    regionName.BGS: ("Bubblegloop Swamp: Inside Mumbo's Skull",),
    regionName.FP: ("Freezeezy Peak: Inside Mumbo's Skull",),
    regionName.MMM: ("Mad Monster Mansion: Inside Mumbos Skull",),     # sic: Lighthouse's name
    regionName.CCW: ("Click Clock Wood: Spring - Inside Mumbo's Skull", "Click Clock Wood: Summer - Inside Mumbo's Skull",
                     "Click Clock Wood: Autumn - Inside Mumbo's Skull"),
}

GAME_BK = 1     # BKBT_AP_GAME_BK: an exit map entry's to_game for this game (include/bkbt.h)


def identity() -> Dict[str, str]:
    """Every door leads to its own world: retail."""
    return {level: level for level in LEVELS}


def is_permutation(world_entrances: Mapping[str, str]) -> bool:
    """Does the mapping put each of the nine worlds behind one of the nine doors?"""
    return (set(world_entrances) == set(LEVELS) and sorted(world_entrances.values()) == sorted(LEVELS))


def exit_map(world_entrances: Mapping[str, str]) -> List[Tuple[int, int, int, int, int, int]]:
    """The hack's exit map for a mapping door -> world: (on_map, og_map, og_exit, to_game, to_map, to_exit) for each
    entry, two for each door d that leads to a world w other than its own: the door's warp, in d's lobby, asks for
    d's world and goes to w; w's exit pad, in w's main map, asks for w's own lobby and goes to d's. Nothing for a
    door that leads to its own world, so the identity is an empty table."""
    if not is_permutation(world_entrances):
        raise ValueError(f"not a world for each of the nine doors: {dict(world_entrances)}")
    entries = []
    for door in DOORS:
        world = DOOR_OF[world_entrances[door.level]]
        if world.level == door.level:
            continue
        entries.append((door.lobby, *door.entrance, GAME_BK, *world.entrance))
        entries.append((world.entrance[0], *world.way_out, GAME_BK, *door.way_out))
    return entries
