# Banjo-Kazooie

## Where is the options page?

The [player options page](../player-options) lets you configure your yaml.

## What does randomization do to this game?

Jiggies, Mumbo Tokens, Bottles' moves, the Lair's note doors and, if you choose, Empty Honeycombs, Jinjos and
Notes are shuffled into the multiworld item pool. Every note you pick up stays picked up, saved with your game,
so a level's notes never have to be collected again. Collecting enough notes for a note door's cost is a check,
and the door itself opens when its item arrives. With `notesanity` every note is a check too, 900 Notes join the
item pool, and the note doors' costs count the Notes you receive instead of the notes you pick up. Each Jinjo is an item of its own level (a Blue
Jinjo of Mumbo's Mountain counts only there); picking a Jinjo up is a check, and once a level's five Jinjo items
have arrived, its Jinjo jiggy appears on Banjo in that level and he takes it at once.

With `randomize_world_entrances` each of the Lair's nine world doors leads into a world drawn for your seed (the
spoiler lists them), and leaving a world takes you back out through the door you came in by. A door keeps its own
picture and podium.

Mumbo's forms come off when Banjo goes into or out of a world. The Lair needs some of them (two witch-switch
jiggies, a podium, the crypt, a Mumbo token): press **D-pad left** in the Lair near the door of a world whose Mumbo
you have paid for that form to take it there (the termite at Mumbo's Mountain's door, the crocodile at Bubblegloop
Swamp's, the walrus at Freezeezy Peak's, the pumpkin at Mad Monster Mansion's, the bee at Click Clock Wood's), and
D-pad left there again to change back. This works with the doors shuffled or not. Inside a world whose Mumbo you
have paid, D-pad left changes Banjo into that world's form, or back, anywhere in it.

Banjo has infinite lives, as in Banjo-Tooie's randomizer: a death never costs a life, so there is no game over.

With `death_link` your deaths go to the other players with death link, and theirs kill Banjo as soon as he can take
it. With `tag_link` every form change by D-pad left is a tag for the other players, and a tag you receive changes
Banjo's form in a world (in the Lair or Spiral Mountain it waits until he is in one). With `max_traps` above 0 traps take the place of
filler: a trip, a slip, Mumbo's sparkle that changes nothing, a face-plant or one of Bottles' tips. Each plays once;
your save remembers the traps it has played.

The other filler is the Blue Egg, Red Feather and Gold Feather Refills: each fills that count to the most it holds,
as the refill pillows in Gruntilda's Lair do, once; your save remembers the refills it has had. There is no Extra Life
item any more, since lives are infinite.

## What is the goal?

Defeat Gruntilda.

## Status

The world generates the whole game, on the logic of HarbourMasters' Lighthouse randomizer, and the
Banjo-Kazooie Client plays it with the ROM it makes from your own Banjo-Kazooie ROM (the setup guide). Not
released yet.
