"""The client's side of the hack's contract: how it finds Banjo-Kazooie in an emulator's RAM, what it writes there
and what it reads back.

The contract is the fork's hack/bk/decomp/include/bkbt.h, layout 0.16.0, and hack/bk/decomp/BKBT.md ("The
Archipelago anchor", "The Archipelago settings", "The Archipelago items", the sections on each kind of location,
"Gruntilda beaten", "Jinjos as Archipelago items and locations", "Notes kept, and notes as Archipelago
locations", "The exit map and the quick transform", "The link: deaths, tags and traps"). In short:
- physical 0x400000 holds the KSEG0 address of the anchor while BK runs, and 0 (or the IPL3's 0xFFFFFFFF before
  BK's first frame, or Tooie's anchor in the dual-boot image) otherwise;
- the anchor points to the settings (the client writes), the items (the client writes), the locations (the
  game writes, the client only reads), the exit map (the client writes) and the link (since 0.15.0: each side
  writes its own fields, the client its requests directly, outside the commit; read_link, write_link);
- the client writes in one order: seed 0 first if the game holds a seed, then skip_intro, notesanity and
  skip_lair_cutscene, then the items, then the exit map, then the seed last, which commits them. Every boot starts
  the settings, the items and the exit map at 0.

Pure Python with nothing but the standard library, so that a tool can load it by path: tools/bk_client_check.py
drives the real game on mupen64plus with Link, the same code the client runs (BKClient.py).

`mem` below is anything with read_u32(address), the N64's big-endian word at a word-aligned address,
write_u8(address, value) and write_u32(address, value), for KSEG0 (0x80xxxxxx) or physical addresses:
emu_loader's EmuLoaderClient is one (it masks bit 31 and puts the bytes in the N64's order), the check tools'
harness another.
"""

from typing import FrozenSet, Iterable, List, NamedTuple, Optional, Tuple

ANCHOR = 0x400000           # physical RDRAM: the anchor's KSEG0 address while BK runs (BKBT.md, "The Archipelago anchor")
MAGIC = 0x424B4150          # 'BKAP', BKBT_AP_MAGIC (include/bkbt.h:458)
GAME_BK = 1                 # BKBT_AP_GAME_BK (include/bkbt.h:459)
WANT = (0, 16)              # the layout this client knows, BKBT_AP_VERSION_MAJOR and _MINOR (include/bkbt.h:461-462)

ANCHOR_SIZE = 32            # sizeof(BkbtApAnchor) (include/bkbt.h:483): +0x0C settings, +0x10 items, +0x14 locations,
                            # +0x18 the exit map (0.13.0; entries for Tooie taken since 0.14.0), +0x1C the link (0.15.0)
SETTINGS_SIZE = 8           # sizeof(BkbtApSettings) (include/bkbt.h:137): +0 u32 seed, +4 u8 skip_intro, +5 u8 notesanity,
                            # +6 u8 skip_lair_cutscene (0.12.0)
ITEMS_SIZE = 96             # sizeof(BkbtApItems) since 0.16.0 (include/bkbt.h:212)
LOCATIONS_SIZE = 464        # sizeof(BkbtApLocations) since 0.11.0 (include/bkbt.h:274)

SEED_AT, SKIP_INTRO_AT, NOTESANITY_AT, SKIP_LAIR_AT = 0x00, 0x04, 0x05, 0x06  # BkbtApSettings (include/bkbt.h:129-137)
MOVE_COUNT = 20                                 # BKBT_AP_MOVE_COUNT, enum ability_e 0..0x13 (include/bkbt.h:157)
MOVES_AT = 0x00                                 # BkbtApItems.moves[20], not 0 = received (include/bkbt.h:201)
HONEYCOMBS_AT = 0x14                            # .honeycombs, the total received (include/bkbt.h:202)
JIGGIES_AT = 0x15                               # .jiggies, the total received (include/bkbt.h:203)
TOKENS_AT = 0x16                                # .tokens, the total received (include/bkbt.h:204)
NOTE_DOORS_AT = 0x18                            # .note_doors[13], by door 1..12, [0] never set (include/bkbt.h:206)
NOTE_DOOR_SLOTS = 13                            # BKBT_AP_NOTE_DOOR_SLOTS (include/bkbt.h:165)
JINJOS_AT = 0x28                                # .jinjos[50], by (enum level_e - 1) * 5 + colour (include/bkbt.h:208)
JINJO_SLOTS = 50                                # BKBT_AP_JINJO_SLOTS (include/bkbt.h:174)
LAIR_JINJOS = range(25, 30)                     # BKBT_AP_JINJO_INDEX(LEVEL_6_LAIR, 0..4): the Lair has no Jinjos
NOTES_AT = 0x5A                                 # .notes, the Notes received, a big-endian u16 (include/bkbt.h:209; 0.11.0)
NOTE_SLOTS = 1000                               # BKBT_AP_NOTE_SLOTS, (enum level_e - 1) * 100 + n (include/bkbt.h:183)
LAIR_NOTES = range(500, 600)                    # BKBT_AP_NOTE_INDEX(LEVEL_6_LAIR, 0..99): the Lair has no notes
REFILLS_AT = 0x5C                               # .refills[4], each kind's total mod 256 (include/bkbt.h:211; 0.16.0)
REFILL_KINDS = 4                                # BKBT_AP_REFILL_KINDS (include/bkbt.h:194): blue eggs, red feathers, gold
                                                # feathers, the less full feather (red or gold)
GOAL_AT = 0x119                                 # BkbtApLocations.gruntilda_beaten (include/bkbt.h:268)
EXIT_SLOTS = 32                                 # BKBT_AP_EXIT_SLOTS (include/bkbt.h:374)
EXIT_SIZE = 12                                  # sizeof(BkbtApExit) (include/bkbt.h:384): u16 on_map, og_map; u8 og_exit,
                                                # to_game; u16 to_map; u8 to_exit
EXITS_SIZE = 388                                # sizeof(BkbtApExits) (include/bkbt.h:389): the entries and a u32 0
GAME_TOOIE = 2                                  # BKBT_AP_GAME_TOOIE (include/bkbt.h:375): to Tooie, taken in a door's game
LINK_SIZE = 20                                  # sizeof(BkbtApLink) (include/bkbt.h:431), since 0.15.0
TRAP_KINDS = 5                                  # BKBT_AP_TRAP_KINDS (include/bkbt.h:414): trip, slip, transform, squish, tip
# BkbtApLink (include/bkbt.h:420-431). The client writes the first three, the game the rest.
DEATHS_REQUESTED_AT = 0x00                      # .deaths_requested (include/bkbt.h:421)
TAGS_REQUESTED_AT = 0x01                        # .tags_requested (include/bkbt.h:422)
TRAPS_AT = 0x02                                 # .traps[5] (include/bkbt.h:423)
DEATHS_AT = 0x08                                # .deaths (include/bkbt.h:425)
DEATHS_APPLIED_AT = 0x09                        # .deaths_applied (include/bkbt.h:426)
TAGS_AT = 0x0A                                  # .tags (include/bkbt.h:427)
TAGS_APPLIED_AT = 0x0B                          # .tags_applied (include/bkbt.h:428)
TRAPS_APPLIED_AT = 0x0C                         # .traps_applied[5] (include/bkbt.h:429)

# The moves every client sends whatever the server gives: camera control and the first note door's lesson, which
# the world has no item for (CLAUDE.md, "BK's Archipelago items"; without 0x13 no note door opens).
ALWAYS_MOVES = (0x03, 0x13)

# The bytes of BkbtApItems the hack reads; the others are padding (include/bkbt.h:200-212).
ITEM_BYTES = (tuple(range(MOVES_AT, MOVES_AT + MOVE_COUNT)) + (HONEYCOMBS_AT, JIGGIES_AT, TOKENS_AT)
              + tuple(range(NOTE_DOORS_AT, NOTE_DOORS_AT + NOTE_DOOR_SLOTS))
              + tuple(range(JINJOS_AT, JINJOS_AT + JINJO_SLOTS)) + (NOTES_AT, NOTES_AT + 1)
              + tuple(range(REFILLS_AT, REFILLS_AT + REFILL_KINDS)))

RDRAM_KSEG0 = range(0x80000000, 0x80800000)     # 8 MiB: the Expansion Pak, which the hack needs


class Group(NamedTuple):
    """One array of the locations: its name is the world's (Locations.LocationData.group)."""
    name: str
    at: int         # offset in BkbtApLocations
    slots: int      # entries in the array: bytes, or bits for a group of bits
    first: int      # the first index that is a location ([0] is never set in the arrays indexed from 1)
    bits: bool = False  # one bit per entry, entry i at byte i >> 3, bit i & 7 (lowest first)


GROUPS = (
    Group("Molehill", 0x00, MOVE_COUNT, 0),     # .moves[20], by the move a molehill teaches (include/bkbt.h:261)
    Group("Honeycomb", 0x14, 0x19, 1),          # .honeycombs[0x19], by enum honeycomb_e (include/bkbt.h:262)
    Group("Jiggy", 0x30, 0x65, 1),              # .jiggies[0x65], by enum jiggy_e (include/bkbt.h:264)
    Group("Mumbo Token", 0x98, 0x74, 1),        # .tokens[0x74], by enum mumbotoken_e (include/bkbt.h:266)
    Group("Note Door", 0x10C, NOTE_DOOR_SLOTS, 1),  # .note_doors[13], a door's threshold by door (include/bkbt.h:267)
    Group("Jinjo", 0x11C, JINJO_SLOTS, 0),      # .jinjos[50], by (level - 1) * 5 + colour (include/bkbt.h:270)
    Group("Note", 0x150, NOTE_SLOTS, 0, True),  # .notes[125], a bit by (level - 1) * 100 + n (include/bkbt.h:272; 0.11.0)
)


class Items(NamedTuple):
    """What the client gives the game: the moves (enum ability_e), the totals received, the note doors (1..12),
    the Jinjos ((enum level_e - 1) * 5 + colour), the Notes received (the game reads them with notesanity) and the
    refills of each kind given to this game (REFILL_KINDS: blue eggs, red feathers, gold feathers, the less full
    feather)."""
    moves: FrozenSet[int] = frozenset()
    honeycombs: int = 0
    jiggies: int = 0
    tokens: int = 0
    note_doors: FrozenSet[int] = frozenset()
    jinjos: FrozenSet[int] = frozenset()
    notes: int = 0
    refills: Tuple[int, int, int, int] = (0, 0, 0, 0)


def items_block(items: Items) -> bytes:
    """The 96 bytes of BkbtApItems the game should hold for `items`, ALWAYS_MOVES included. A total above 255 is
    written as 255 (the game reads more than it has as all it has: 24 honeycombs, 100 jiggies, 115 tokens), the
    Notes above 0xFFFF as 0xFFFF (it reads at most 900), and the refills mod 256 (the game applies a kind whose total
    is ahead of the count it has applied, mod 256)."""
    if not all(0 <= m < MOVE_COUNT for m in items.moves):
        raise ValueError(f"moves are 0..{MOVE_COUNT - 1} (enum ability_e): {sorted(items.moves)}")
    if not all(1 <= d < NOTE_DOOR_SLOTS for d in items.note_doors):
        raise ValueError(f"note doors are 1..{NOTE_DOOR_SLOTS - 1}: {sorted(items.note_doors)}")
    if not all(0 <= j < JINJO_SLOTS and j not in LAIR_JINJOS for j in items.jinjos):
        raise ValueError(f"Jinjos are 0..{JINJO_SLOTS - 1} without the Lair's 25..29: {sorted(items.jinjos)}")
    if len(items.refills) != REFILL_KINDS:
        raise ValueError(f"the refills are {REFILL_KINDS} totals: {items.refills}")
    if min(items.honeycombs, items.jiggies, items.tokens, items.notes, *items.refills) < 0:
        raise ValueError("a total is never below 0")
    block = bytearray(ITEMS_SIZE)
    for m in set(items.moves) | set(ALWAYS_MOVES):
        block[MOVES_AT + m] = 1
    block[HONEYCOMBS_AT] = min(0xFF, items.honeycombs)
    block[JIGGIES_AT] = min(0xFF, items.jiggies)
    block[TOKENS_AT] = min(0xFF, items.tokens)
    for d in items.note_doors:
        block[NOTE_DOORS_AT + d] = 1
    for j in items.jinjos:
        block[JINJOS_AT + j] = 1
    block[NOTES_AT:NOTES_AT + 2] = min(0xFFFF, items.notes).to_bytes(2, "big")
    for kind, total in enumerate(items.refills):
        block[REFILLS_AT + kind] = total & 0xFF
    return bytes(block)


class Exit(NamedTuple):
    """One entry of the exit map: a map change asked for while Banjo is in on_map, to og_map at og_exit, goes to
    to_map at to_exit in to_game (GAME_BK, this game; GAME_TOOIE, Tooie, in its numbering, since layout 0.14.0, in a
    game a door started)."""
    on_map: int
    og_map: int
    og_exit: int
    to_game: int
    to_map: int
    to_exit: int


def exits_block(exits: Iterable[Exit]) -> bytes:
    """The 388 bytes of BkbtApExits the game should hold for `exits`: the entries in order, the rest 0, which ends
    the table."""
    exits = list(exits)
    if len(exits) > EXIT_SLOTS:
        raise ValueError(f"the exit map holds {EXIT_SLOTS} entries, not {len(exits)}")
    block = bytearray(EXITS_SIZE)
    for i, e in enumerate(exits):
        if not 0 < e.on_map <= 0xFFFF or not 0 <= e.og_map <= 0xFFFF or not 0 <= e.to_map <= 0xFFFF:
            raise ValueError(f"an entry's maps are u16, on_map not 0: {e}")
        if not all(0 <= b <= 0xFF for b in (e.og_exit, e.to_game, e.to_exit)):
            raise ValueError(f"an entry's exits and game are bytes: {e}")
        at = i * EXIT_SIZE
        block[at:at + 2] = e.on_map.to_bytes(2, "big")
        block[at + 2:at + 4] = e.og_map.to_bytes(2, "big")
        block[at + 4], block[at + 5] = e.og_exit, e.to_game
        block[at + 6:at + 8] = e.to_map.to_bytes(2, "big")
        block[at + 8] = e.to_exit
    return bytes(block)


def is_pointer(value: int, size: int) -> bool:
    """A KSEG0 address of `size` bytes in RDRAM, on a word."""
    return value in RDRAM_KSEG0 and value + size <= RDRAM_KSEG0.stop and value % 4 == 0


def read_block(mem, address: int, n: int) -> bytes:
    """n bytes from a word-aligned address, a word at a time."""
    return b"".join(mem.read_u32(address + i).to_bytes(4, "big") for i in range(0, n, 4))[:n]


def validate(pm, rdram_base: int) -> bool:
    """EmuLoader's validation_func: is `rdram_base` the start of RDRAM with BK's anchor published? It reads the
    process's memory directly, where RDRAM is held a word at a time in the host's (little-endian) order, as Tooie's
    validate_bt_signature does (Archipelago-BanjoTooie/worlds/banjo_tooie/BTClient.py:97). Only the magic and the
    game id: the layout is checked once connected (find), so that an old ROM gets a message instead of silence."""
    try:
        word = int.from_bytes(pm.read_bytes(rdram_base + ANCHOR, 4), "little")
        if not is_pointer(word, ANCHOR_SIZE):
            return False
        at = rdram_base + (word - RDRAM_KSEG0.start)
        magic = int.from_bytes(pm.read_bytes(at, 4), "little")
        game = int.from_bytes(pm.read_bytes(at + 4, 4), "little") >> 24
    except Exception:
        return False
    return magic == MAGIC and game == GAME_BK


class Found(NamedTuple):
    """The anchor as found: its address, the layout and the five blocks' KSEG0 addresses."""
    anchor: int
    version: Tuple[int, int, int]
    settings: int
    items: int
    locations: int
    exits: int
    link: int


class NotReady(Exception):
    """Nothing to write to or read from now. `waiting`: an ordinary state that passes by itself (BK not running
    yet, Tooie running, a switch between the games); otherwise the ROM is not one this client can play."""

    def __init__(self, reason: str, waiting: bool = True):
        super().__init__(reason)
        self.reason, self.waiting = reason, waiting


def find(mem) -> Found:
    """Follow the anchor, or raise NotReady with the reason."""
    word = mem.read_u32(ANCHOR)
    if not is_pointer(word, ANCHOR_SIZE):
        raise NotReady("Banjo-Kazooie is not running (nothing published at 0x400000)")
    head = read_block(mem, word, ANCHOR_SIZE)
    magic, game = int.from_bytes(head[0:4], "big"), head[4]
    size, major = int.from_bytes(head[6:8], "big"), int.from_bytes(head[8:10], "big")
    version = (major, head[10], head[11])
    if magic != MAGIC or game != GAME_BK:
        raise NotReady("another game runs (Banjo-Tooie in the dual-boot image, or a switch between the games)")
    text = ".".join(map(str, version))
    if major != WANT[0]:
        raise NotReady(f"the ROM's layout is {text}, which this client does not know: update the client", False)
    if version[1] < WANT[1]:
        raise NotReady(f"the ROM's layout is {text}; this client needs {WANT[0]}.{WANT[1]} or later: "
                       f"build the ROM again from the fork (bash hack/build_bk_rom.sh)", False)
    if size < ANCHOR_SIZE:
        raise NotReady(f"the anchor is {size} bytes, {ANCHOR_SIZE} in layout {WANT[0]}.{WANT[1]}: a broken build", False)
    settings, items, locations, exits, link = (int.from_bytes(head[i:i + 4], "big")
                                                for i in (0x0C, 0x10, 0x14, 0x18, 0x1C))
    for name, at, n in (("settings", settings, SETTINGS_SIZE), ("items", items, ITEMS_SIZE),
                        ("locations", locations, LOCATIONS_SIZE), ("exit map", exits, EXITS_SIZE),
                        ("link", link, LINK_SIZE)):
        if not is_pointer(at, n):
            raise NotReady(f"the anchor's {name} address 0x{at:08X} is not in RDRAM: a broken build", False)
    return Found(word, version, settings, items, locations, exits, link)


def read_settings(mem, found: Found) -> Tuple[int, int, int, int]:
    """(seed, skip_intro, notesanity, skip_lair_cutscene) as the game holds them."""
    word = mem.read_u32(found.settings + SKIP_INTRO_AT)
    return mem.read_u32(found.settings + SEED_AT), word >> 24, (word >> 16) & 0xFF, (word >> 8) & 0xFF


def holds(held: bytes, block: bytes) -> bool:
    """Does the game hold `block`? Only the bytes the hack reads count."""
    return all(held[i] == block[i] for i in ITEM_BYTES)


def commit(mem, found: Found, seed: int, skip_intro: bool, block: bytes, notesanity: bool = False,
           skip_lair_cutscene: bool = True, exits: bytes = bytes(EXITS_SIZE)) -> bool:
    """Make the game hold this seed, skip_intro, notesanity, skip_lair_cutscene, items (items_block) and exit map
    (exits_block), in the contract's order. Writes nothing and returns False when the game already holds them; True
    when it wrote."""
    if not 0 < seed <= 0xFFFFFFFF:
        raise ValueError("the seed is 1..0xFFFFFFFF: 0 means no client")
    skip = 1 if skip_intro else 0
    sanity = 1 if notesanity else 0
    lair = 1 if skip_lair_cutscene else 0
    had_seed, had_skip, had_sanity, had_lair = read_settings(mem, found)
    held = read_block(mem, found.items, ITEMS_SIZE)
    held_exits = read_block(mem, found.exits, EXITS_SIZE)
    if (had_seed == seed and had_skip == skip and had_sanity == sanity and had_lair == lair and holds(held, block)
            and held_exits == exits):
        return False
    if mem.read_u32(ANCHOR) != found.anchor:
        return False                    # BK went away since find (a reset, a switch to Tooie): write nothing
    if had_seed:
        mem.write_u32(found.settings + SEED_AT, 0)  # a change in a running game: uncommit first
    if had_skip != skip:
        mem.write_u8(found.settings + SKIP_INTRO_AT, skip)
    if had_sanity != sanity:
        mem.write_u8(found.settings + NOTESANITY_AT, sanity)
    if had_lair != lair:
        mem.write_u8(found.settings + SKIP_LAIR_AT, lair)
    for i in ITEM_BYTES:                # the client is the items' only writer, so only what differs
        if held[i] != block[i]:
            mem.write_u8(found.items + i, block[i])
    for i in range(0, EXITS_SIZE, 4):   # and the exit map's, a word at a time (it is on a word)
        if held_exits[i:i + 4] != exits[i:i + 4]:
            mem.write_u32(found.exits + i, int.from_bytes(exits[i:i + 4], "big"))
    mem.write_u32(found.settings + SEED_AT, seed)  # last: commits
    return True


class LinkState(NamedTuple):
    """The link block, BkbtApLink, as the game holds it (include/bkbt.h:420-431): the client's requests, and what
    the game did."""
    deaths_requested: int
    tags_requested: int
    traps: Tuple[int, ...]
    deaths: int
    deaths_applied: int
    tags: int
    tags_applied: int
    traps_applied: Tuple[int, ...]


def read_link(mem, found: Found) -> LinkState:
    block = read_block(mem, found.link, LINK_SIZE)
    return LinkState(block[DEATHS_REQUESTED_AT], block[TAGS_REQUESTED_AT],
                     tuple(block[TRAPS_AT:TRAPS_AT + TRAP_KINDS]), block[DEATHS_AT], block[DEATHS_APPLIED_AT],
                     block[TAGS_AT], block[TAGS_APPLIED_AT],
                     tuple(block[TRAPS_APPLIED_AT:TRAPS_APPLIED_AT + TRAP_KINDS]))


def write_link(mem, found: Found, held: LinkState, deaths_requested: int, tags_requested: int,
               traps: Iterable[int]) -> bool:
    """The client's fields of the link, a byte each where they differ from `held`, written directly: the game acts on
    them only while the seed is committed, and they must not uncommit the items. Nothing when BK went away since find.
    True when it wrote."""
    traps = tuple(min(0xFF, max(0, t)) for t in traps)
    if len(traps) != TRAP_KINDS:
        raise ValueError(f"the traps are {TRAP_KINDS} totals, by kind")
    wanted = [(DEATHS_REQUESTED_AT, deaths_requested & 0xFF, held.deaths_requested),
              (TAGS_REQUESTED_AT, tags_requested & 0xFF, held.tags_requested)]
    wanted += [(TRAPS_AT + k, traps[k], held.traps[k]) for k in range(TRAP_KINDS)]
    writes = [(at, value) for at, value, had in wanted if value != had]
    if not writes or mem.read_u32(ANCHOR) != found.anchor:
        return False
    for at, value in writes:
        mem.write_u8(found.link + at, value)
    return True


class Published(NamedTuple):
    """What the game publishes: the checks as (group, hack id), and the goal."""
    checks: FrozenSet[Tuple[str, int]]
    goal: bool
    empty: bool     # every byte 0: no file chosen (boot, file select, demos), or a file with nothing done yet


def read_published(mem, found: Found) -> Published:
    block = read_block(mem, found.locations, LOCATIONS_SIZE)
    checks = frozenset((g.name, i) for g in GROUPS for i in range(g.first, g.slots)
                       if (block[g.at + (i >> 3)] >> (i & 7) & 1 if g.bits else block[g.at + i]))
    goal = block[GOAL_AT] != 0
    return Published(checks, goal, not checks and not goal)


class Tick(NamedTuple):
    """One poll's outcome. state: "waiting" (no BK to talk to), "refused" (a ROM this client cannot play),
    "no seed" (BK found, no server slot yet), "foreign" (the game may be playing a file of another seed) or
    "ready". Only "ready" writes (committed: it wrote this poll) and reports checks and the goal."""
    state: str
    reason: str
    checks: FrozenSet[Tuple[str, int]] = frozenset()
    goal: bool = False
    committed: bool = False


class Link:
    """What the client does on each poll, without the network (BKClient.py adds the server).

    A file is bound to the seed it was started with (BKBT.md, "The Archipelago settings"), but what the game
    publishes is the file being played, whatever seed is committed now, and the items committed go into that file
    and its save. So when the client sees the game holding another seed (another slot's client ran, or this client
    changed slots), the file being played may be another slot's: the client writes nothing and reports nothing
    ("foreign") until it sees the locations empty, which they are at every boot and at the file select
    (clearScoreStates). Then it commits its own seed, and from there on a file loads only when it is empty or bound
    to this seed. One case gets past this: a file of the other seed just started, with nothing done in it yet,
    reads empty too. The hack does not publish which seed the file being played is bound to (bkbt_playing_seed);
    publishing it would close that."""

    def __init__(self) -> None:
        self.found: Optional[Found] = None
        self.seed: Optional[int] = None     # the seed `foreign` was decided against
        self.foreign = False
        self.commits = 0
        self.last = Tick("waiting", "not looked yet")

    def tick(self, mem, seed: Optional[int], skip_intro: bool, items: Items, notesanity: bool = False,
             skip_lair_cutscene: bool = True, exits: Iterable[Exit] = ()) -> Tick:
        self.last = self._tick(mem, seed, skip_intro, items, notesanity, skip_lair_cutscene, exits)
        return self.last

    def _tick(self, mem, seed, skip_intro, items, notesanity, skip_lair_cutscene, exits) -> Tick:
        try:
            found = find(mem)
        except NotReady as e:
            self.found = None
            return Tick("waiting" if e.waiting else "refused", e.reason)
        self.found = found
        if not seed:
            return Tick("no seed", "not connected to a slot on an Archipelago server: nothing is written or sent "
                                   "until then (a game in progress keeps what it holds, and its checks wait)")
        if seed != self.seed:
            # Another slot: decided again. The game's seed then says whose file is played, as this client
            # wrote nothing while it was foreign (the file was loaded under the seed the game still holds).
            self.seed, self.foreign = seed, False
        had_seed = read_settings(mem, found)[0]
        if had_seed not in (0, seed):
            self.foreign = True
        if self.foreign:
            if not read_published(mem, found).empty:
                return Tick("foreign", "the game may be playing a file of another seed: Save and Quit (or reset), "
                                       "then choose a file of this seed; until then the client writes and sends nothing")
            self.foreign = False
        committed = commit(mem, found, seed, skip_intro, items_block(items), notesanity, skip_lair_cutscene,
                           exits_block(exits))
        self.commits += committed
        published = read_published(mem, found)
        return Tick("ready", "playing", published.checks, published.goal, committed)


def describe(items: Items) -> str:
    """The items as a line of text, for the client's /bk command."""
    moves = sorted(set(items.moves) | set(ALWAYS_MOVES))
    return (f"moves {', '.join(f'0x{m:X}' for m in moves)}; {items.honeycombs} honeycombs, {items.jiggies} jiggies, "
            f"{items.tokens} tokens; note doors {', '.join(map(str, sorted(items.note_doors))) or 'none'}; "
            f"{len(items.jinjos)} Jinjos, {items.notes} Notes; refills {'/'.join(map(str, items.refills))}")


def check_names(checks: Iterable[Tuple[str, int]]) -> List[str]:
    """(group, hack id) as text, for logs."""
    return [f"{g} 0x{i:X}" for g, i in sorted(checks)]

