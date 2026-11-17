# Setup Guide for Banjo-Kazooie Archipelago

Playable for testing, not yet released. For both games in one slot, see the Banjo-Kazooie & Tooie world's guide.

## What you need

- Your own Banjo-Kazooie (USA) ROM, version 1.0 (`.z64`, `.v64` or `.n64`). The client makes the ROM you play from
  it.
- Project64 3.0.1 or ares v148 (other emulators that EmuLoader attaches to may work, untried), with the
  Expansion Pak.
- The Banjo-Kazooie Client, from the Archipelago Launcher. Nothing else to install: the apworld carries EmuLoader,
  which the client reaches the emulator with.

## Making the ROM

The first time the Banjo-Kazooie Client starts, it asks for your Banjo-Kazooie ROM and makes
`Banjo-Kazooie AP <version>.z64` from it, in about ten seconds; its log says where (Archipelago's folder, unless you
set another with `/patch_path`). It makes it again only when a new version of the world needs a new ROM. `/patch`
makes it if it is missing, `/rom_path` changes which ROM it is made from, and `/autostart` starts your emulator with
it.

## Playing

1. Connect the Banjo-Kazooie Client to the server (`/connect <address>`) and enter your slot name.
2. Start `Banjo-Kazooie AP <version>.z64` in the emulator. The client attaches once Banjo-Kazooie runs.
3. On Banjo-Kazooie's file select, start a new game. A file is bound to the slot it was started with: a
   file of another slot cannot be loaded. Without the client, no game starts.

`/bk` in the client shows what it sees and what it gives the game.
