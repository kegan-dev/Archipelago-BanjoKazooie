"""The emulator connection's package, emu_loader (EmuLoader 0.1.4 by Killklli, MIT).

The installed package when there is one (a source checkout of Archipelago, where the Banjo-Tooie world's
requirements.txt installs it), else the copy the Banjo-Kazooie world carries (worlds/banjo_kazooie/emu_loader/,
unchanged, its LICENSE beside it), which is what an installed Archipelago has: it cannot pip install. The copy needs
only the standard library and reads its emulators.json through importlib.resources, so it works from inside the
zipped apworld.

When the copy is taken it is also given the name emu_loader, its modules too, so that code which imports the package
by its name finds it: the stock Banjo-Tooie client (`from emu_loader import ...`,
Archipelago-BanjoTooie/worlds/banjo_tooie/BTClient.py:16-21), which the combined client runs, then uses the same
copy, and the combined world needs nothing of the Banjo-Tooie apworld's own copy. The combined client loads it before
it imports BTClient.
"""

import importlib
import sys
from types import ModuleType

NAME = "emu_loader"


def load() -> ModuleType:
    """emu_loader: the installed package, else this world's copy, from then on also under the package's name."""
    try:
        return importlib.import_module(NAME)
    except ImportError:
        pass
    from .. import emu_loader as copy
    prefix = copy.__name__ + "."
    sys.modules[NAME] = copy
    for name, module in list(sys.modules.items()):
        if name.startswith(prefix):
            sys.modules[f"{NAME}.{name[len(prefix):]}"] = module
    return copy
