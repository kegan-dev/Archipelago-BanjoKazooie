# emu_loader, a copy

EmuLoader 0.1.4 by Killklli, the emulator-memory package the Banjo-Kazooie clients reach the emulator with, copied
here unchanged so that the apworld carries it: an installed Archipelago cannot pip install a package, and the BK world
depends on no other world for it.

- Source: <https://github.com/Killklli/EmuLoader>, tag `v0.1.4`, commit `61125e503d1e6c5ed853de1d15684ff2bc680311`
  (the wheel `pip install "emu-loader @ git+https://github.com/Killklli/EmuLoader@v0.1.4"` makes).
- License: MIT, `LICENSE` beside this file (the package's own), which must ship with the copy.
- Unchanged: `worlds/banjo_kazooie/test/test_client.py` (`TestEmuLoaderPlaces`) checks every file against the sha256
  of the wheel's `RECORD`.
- Used through `worlds/banjo_kazooie/client/emu.py`: the installed package when there is one, else this copy.

To take a newer release: replace the files with the new wheel's, `LICENSE` included, and the hashes in the test.
