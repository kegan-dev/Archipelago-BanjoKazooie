"""The world's option presets (WebWorld.options_presets): Archipelago's Launcher ("Generate Template Options") and
tools/make_apworlds.py write a template yaml for each, with every option and these values chosen."""

from typing import Any, Dict

# The alpha with friends in a multiworld (docs/ROADMAP.md, "The owner's next items", 8; the owner's choices of
# 2026-11-15). The owner chose them for the combined world's slot (worlds/banjo_kazooie_tooie/Presets.py); a player
# of Banjo-Kazooie alone gets the same: Spiral Mountain's nine moves at the start and the other nine shuffled (the
# combined world's randomize_bk_moves spiral_mountain), and every door leading into its own world.
ALPHA: Dict[str, Any] = {
    "randomize_moves": True,
    "start_with_spiral_mountain_moves": True,
    "randomize_world_entrances": False,
}

options_presets: Dict[str, Dict[str, Any]] = {
    "Alpha": ALPHA,
}
