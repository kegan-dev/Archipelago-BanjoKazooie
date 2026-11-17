"""The client without an emulator or a server: client/hack.py against a fake RAM laid out as the hack lays it out,
client/ids.py against the world's tables, hack.py's offsets against the fork's include/bkbt.h, and BKClient.poll with
a stand-in for the server. tools/bk_client_check.py runs the same code against the real game on mupen64plus."""

import asyncio
import re
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from NetUtils import ClientStatus, NetworkItem

from .. import Entrances
from ..Items import all_item_table, jinjo_table, moves_table, note_door_table
from ..Locations import all_location_table, vanilla_jinjos, vanilla_molehill_moves
from ..Names import itemName
from ..client import hack, ids
from ..client.link import LinkDriver, Sent

ANCHOR_AT = 0x80300000          # where the fake game keeps its anchor (any KSEG0 word in RDRAM)
SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, EXITS_AT = 0x80300100, 0x80300200, 0x80300400, 0x80300800
LINK_AT = 0x80300A00
SEED = 0x5EED0B0B
GOAL = 0x119                    # bkbt_ap_locations.gruntilda_beaten (the fork's include/bkbt.h:268), not hack.GOAL_AT
JINJOS = 0x11C                  # bkbt_ap_locations.jinjos (include/bkbt.h:270); items .jinjos at +0x28 (include/bkbt.h:208)
NOTES = 0x150                   # bkbt_ap_locations.notes, a bit per note (include/bkbt.h:272); items .notes at +0x5A (include/bkbt.h:209)
MM_BLUE = "Blue Jinjo (Mumbo's Mountain)"


def note_name(index: int) -> str:
    """The world's location of the note whose hack index is `index`."""
    return next(name for name, data in all_location_table.items() if data.group == "Note" and data.hack_id == index)


def put_note(ram, index: int) -> None:
    """The game publishes note `index` picked up: its bit in bkbt_ap_locations.notes."""
    at = LOCATIONS_AT + NOTES + (index >> 3)
    ram.put(at, bytes((ram.get(at, 1)[0] | 1 << (index & 7),)))


class FakeRAM:
    """RDRAM as the client sees it through EmuLoader: big-endian words, KSEG0 or physical addresses. The client's
    writes are recorded with the seed the game held just before each one."""

    def __init__(self) -> None:
        self.words: Dict[int, int] = {}
        self.writes: List[Tuple[str, int, int, int]] = []   # (kind, physical address, value, seed before)

    @staticmethod
    def phys(address: int) -> int:
        return address & 0x7FFFFFFF     # EmuLoader masks bit 31 (emu_loader/emulatorinfo.py, readBytes)

    def read_u32(self, address: int) -> int:
        assert address % 4 == 0, hex(address)
        return self.words.get(self.phys(address), 0)

    def _seed(self) -> int:
        return self.words.get(self.phys(SETTINGS_AT), 0)

    def write_u32(self, address: int, value: int) -> None:
        assert address % 4 == 0, hex(address)
        self.writes.append(("u32", self.phys(address), value, self._seed()))
        self.words[self.phys(address)] = value & 0xFFFFFFFF

    def write_u8(self, address: int, value: int) -> None:
        self.writes.append(("u8", self.phys(address), value, self._seed()))
        self.put(address, bytes((value,)))

    # the game's side: not recorded
    def put(self, address: int, data: bytes) -> None:
        for i, b in enumerate(data):
            a = self.phys(address + i)
            word = self.words.get(a & ~3, 0)
            shift = 8 * (3 - (a & 3))
            self.words[a & ~3] = (word & ~(0xFF << shift)) | b << shift

    def get(self, address: int, n: int) -> bytes:
        return bytes((self.words.get(self.phys(address + i) & ~3, 0) >> 8 * (3 - ((address + i) & 3))) & 0xFF
                     for i in range(n))


def bk_game(version=(0, 16, 0), size=32, magic=hack.MAGIC, game=hack.GAME_BK, pointers=None) -> FakeRAM:
    """A BK that has booted: its anchor published, settings, items, locations, exit map and link all 0."""
    ram = FakeRAM()
    pointers = pointers or (SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, EXITS_AT, LINK_AT)
    ram.put(ANCHOR_AT, magic.to_bytes(4, "big") + bytes((game, 0)) + size.to_bytes(2, "big")
            + version[0].to_bytes(2, "big") + bytes(version[1:]) + b"".join(p.to_bytes(4, "big") for p in pointers))
    ram.words[hack.ANCHOR] = ANCHOR_AT
    return ram


class HostMemory:
    """An emulator process's memory as validate reads it: RDRAM a word at a time in the host's order."""

    def __init__(self, ram: FakeRAM, base: int = 0x10000000) -> None:
        self.base = base
        self.data = {base + a + i: b for a, w in ram.words.items() for i, b in enumerate(w.to_bytes(4, "little"))}

    def read_bytes(self, address: int, n: int) -> bytes:
        return bytes(self.data.get(address + i, 0) for i in range(n))


class TestFind(unittest.TestCase):
    def test_finds_the_anchor(self) -> None:
        found = hack.find(bk_game())
        self.assertEqual(found, hack.Found(ANCHOR_AT, (0, 16, 0), SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, EXITS_AT,
                                           LINK_AT))

    def test_newer_minor_is_read(self) -> None:
        self.assertEqual(hack.find(bk_game(version=(0, 17, 2), size=36)).version, (0, 17, 2))

    def test_waits_without_an_anchor(self) -> None:
        for word in (0, 0xFFFFFFFF, 0x80300002):
            ram = bk_game()
            ram.words[hack.ANCHOR] = word
            with self.assertRaises(hack.NotReady) as e:
                hack.find(ram)
            self.assertTrue(e.exception.waiting, hex(word))

    def test_waits_while_another_game_runs(self) -> None:
        for ram in (bk_game(magic=0x80123456), bk_game(game=2)):
            with self.assertRaises(hack.NotReady) as e:
                hack.find(ram)
            self.assertTrue(e.exception.waiting)

    def test_refuses_other_layouts(self) -> None:
        for kw in (dict(version=(0, 15, 0)), dict(version=(0, 14, 0)), dict(version=(0, 13, 0)), dict(version=(0, 12, 0)), dict(version=(0, 11, 0)), dict(version=(0, 10, 0)),
                   dict(version=(0, 9, 0)), dict(version=(0, 8, 0)), dict(version=(1, 0, 0)), dict(size=20), dict(size=24),
                   dict(size=28),
                   dict(pointers=(SETTINGS_AT, 0x00300200, LOCATIONS_AT, EXITS_AT, LINK_AT)),
                   dict(pointers=(SETTINGS_AT, ITEMS_AT, 0x807FFF00, EXITS_AT, LINK_AT)),
                   dict(pointers=(SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, 0x80300802, LINK_AT)),
                   dict(pointers=(SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, 0x807FFF00, LINK_AT)),
                   dict(pointers=(SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, EXITS_AT, 0x80300A02)),
                   dict(pointers=(SETTINGS_AT, ITEMS_AT, LOCATIONS_AT, EXITS_AT, 0x807FFFF8))):
            with self.assertRaises(hack.NotReady) as e:
                hack.find(bk_game(**kw))
            self.assertFalse(e.exception.waiting, kw)

    def test_validate(self) -> None:
        self.assertTrue(hack.validate(HostMemory(bk_game()), 0x10000000))
        self.assertTrue(hack.validate(HostMemory(bk_game(version=(0, 8, 0))), 0x10000000))  # find refuses it, later
        self.assertFalse(hack.validate(HostMemory(bk_game()), 0x10001000))
        self.assertFalse(hack.validate(HostMemory(bk_game(magic=0x80123456)), 0x10000000))
        none = bk_game()
        none.words[hack.ANCHOR] = 0xFFFFFFFF
        self.assertFalse(hack.validate(HostMemory(none), 0x10000000))


class TestItems(unittest.TestCase):
    def test_block(self) -> None:
        block = hack.items_block(hack.Items(frozenset({0x00, 0x10}), 30, 300, 5, frozenset({1, 8}), frozenset({0, 49}),
                                            810, (1, 2, 300, 0)))
        self.assertEqual(len(block), hack.ITEMS_SIZE)
        self.assertEqual({i for i in range(20) if block[i]}, {0x00, 0x03, 0x10, 0x13})   # camera, note doors always
        self.assertEqual((block[0x14], block[0x15], block[0x16]), (30, 255, 5))
        self.assertEqual({d for d in range(13) if block[0x18 + d]}, {1, 8})
        self.assertEqual({j for j in range(50) if block[0x28 + j]}, {0, 49})
        self.assertEqual(block[0x5A:0x5C], (810).to_bytes(2, "big"))         # the Notes received, big-endian
        self.assertEqual(block[0x5C:0x60], bytes((1, 2, 300 & 0xFF, 0)))       # the refills, mod 256
        self.assertFalse(any(block[i] for i in range(hack.ITEMS_SIZE) if i not in hack.ITEM_BYTES))
        self.assertEqual(hack.items_block(hack.Items(notes=70000))[0x5A:0x5C], b"\xff\xff")

    def test_refuses_what_the_hack_has_no_byte_for(self) -> None:
        for items in (hack.Items(moves=frozenset({20})), hack.Items(note_doors=frozenset({0})),
                      hack.Items(note_doors=frozenset({13})), hack.Items(jiggies=-1), hack.Items(jinjos=frozenset({25})),
                      hack.Items(jinjos=frozenset({50})), hack.Items(notes=-1), hack.Items(refills=(1, 2, 3)),
                      hack.Items(refills=(0, -1, 0, 0))):
            with self.assertRaises(ValueError):
                hack.items_block(items)

    def test_items_of_names(self) -> None:
        names = ([itemName.JIGGY] * 3 + [itemName.EMPTY_HONEYCOMB] * 7 + [itemName.MUMBO_TOKEN] * 2
                 + [itemName.TALON_TROT, itemName.BEAK_BARGE, itemName.NOTE_DOORS[1], itemName.EXTRA_LIFE, None,
                    MM_BLUE, "Yellow Jinjo (Mad Monster Mansion)"] + [itemName.NOTE] * 4
                 + [itemName.BLUE_EGG_REFILL] * 2 + [itemName.GOLD_FEATHER_REFILL])
        items, skipped = ids.items_of(names)
        self.assertEqual(items, hack.Items(frozenset({0x10, 0x00}), 7, 3, 2, frozenset({2}), frozenset({0, 49}), 4,
                                           (2, 0, 1, 0)))
        self.assertEqual(skipped, {itemName.EXTRA_LIFE: 1, None: 1})

    def test_every_item_is_known(self) -> None:
        totals = {itemName.JIGGY, itemName.EMPTY_HONEYCOMB, itemName.MUMBO_TOKEN, itemName.NOTE}
        for name in all_item_table:
            self.assertEqual(sum((name in ids.MOVE_OF, name in ids.NOTE_DOOR_OF, name in ids.JINJO_OF, name in totals,
                                  name in ids.NOTHING_FOR, name in ids.TRAP_OF, name in ids.REFILL_OF)), 1, name)
        self.assertEqual(set(ids.MOVE_OF), set(moves_table))
        self.assertEqual(set(ids.NOTE_DOOR_OF), set(note_door_table))
        self.assertEqual(set(ids.JINJO_OF), set(jinjo_table))

    def test_a_move_is_its_molehills(self) -> None:
        # unshuffled, a molehill holds its own move: the move's ability is the molehill's hack id
        for location, move in vanilla_molehill_moves.items():
            self.assertEqual(ids.MOVE_OF[move], all_location_table[location].hack_id, location)

    def test_a_jinjo_is_its_location(self) -> None:
        # unshuffled, a Jinjo holds itself: the Jinjo's hack id is its location's
        self.assertEqual(len(vanilla_jinjos), 45)
        for location, jinjo in vanilla_jinjos.items():
            self.assertEqual(ids.JINJO_OF[jinjo], all_location_table[location].hack_id, location)


class TestLocations(unittest.TestCase):
    def test_every_location_maps(self) -> None:
        world = {(data.group, data.hack_id): data.bkid for data in all_location_table.values()}
        self.assertEqual(ids.LOCATION_OF, world)
        self.assertEqual({g.name for g in hack.GROUPS}, {data.group for data in all_location_table.values()})

    def test_published(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        self.assertEqual(hack.read_published(ram, found), hack.Published(frozenset(), False, True))
        for at in (0x00, 0x14 + 1, 0x30 + 0x64, 0x98 + 0x73, 0x10C + 8, 0x10C + 12, JINJOS + 0, JINJOS + 49):
            ram.put(LOCATIONS_AT + at, b"\x01")
        ram.put(LOCATIONS_AT + 0x14, b"\x01")       # honeycombs[0], never set by the game, is no location
        ram.put(LOCATIONS_AT + 0x2D, b"\x01")       # padding
        ram.put(LOCATIONS_AT + 0x14E, b"\x01")      # padding behind the Jinjos
        for index in (0, 999, 500):                 # MM's note 0, MMM's 99, and the Lair's 0, which the game never sets
            put_note(ram, index)
        ram.put(LOCATIONS_AT + 0x1CD, b"\x01")      # padding behind the notes
        published = hack.read_published(ram, found)
        self.assertEqual(published.checks, {("Molehill", 0), ("Honeycomb", 1), ("Jiggy", 0x64), ("Mumbo Token", 0x73),
                                            ("Note Door", 8), ("Note Door", 12), ("Jinjo", 0), ("Jinjo", 49),
                                            ("Note", 0), ("Note", 999), ("Note", 500)})
        self.assertFalse(published.goal)
        self.assertEqual({ids.location_of(*c) for c in published.checks} - {None}, {
            all_location_table["SM: Bottles (Beak Barge)"].bkid, all_location_table["GL: Note Door 8 Threshold"].bkid,
            all_location_table["MM: Jinjo (Blue)"].bkid, all_location_table["MMM: Jinjo (Yellow)"].bkid,
            all_location_table[note_name(0)].bkid, all_location_table[note_name(999)].bkid,
            *(data.bkid for data in all_location_table.values()
              if (data.group, data.hack_id) in {("Honeycomb", 1), ("Jiggy", 0x64), ("Mumbo Token", 0x73)})})
        self.assertIsNone(ids.location_of("Note Door", 12))     # doors 9..12 guard nothing
        self.assertIsNone(ids.location_of("Jinjo", 25))         # the Lair has no Jinjos
        self.assertIsNone(ids.location_of("Note", 500))         # nor notes
        ram.put(LOCATIONS_AT + GOAL, b"\x01")
        self.assertTrue(hack.read_published(ram, found).goal)


class TestCommit(unittest.TestCase):
    block = hack.items_block(hack.Items(frozenset({0x10}), 2, 1, 0, frozenset({1})))

    def assert_contract_order(self, ram: FakeRAM, uncommit_first: bool) -> None:
        writes = ram.writes
        self.assertEqual(writes[-1][:3], ("u32", ram.phys(SETTINGS_AT), SEED), "the seed is written last")
        body = writes[:-1]
        if uncommit_first:
            self.assertEqual(body[0][:3], ("u32", ram.phys(SETTINGS_AT), 0), "seed 0 first over a committed seed")
            body = body[1:]
        for kind, address, value, seed_before in body:
            self.assertEqual(seed_before, 0, f"{kind} 0x{address:X} = {value} written while a seed was committed")
            self.assertNotEqual(address, ram.phys(SETTINGS_AT), "the seed is written only first (0) and last")

    def test_after_a_boot(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block))
        self.assert_contract_order(ram, uncommit_first=False)
        self.assertEqual(ram.get(ITEMS_AT, hack.ITEMS_SIZE), self.block)
        self.assertEqual(hack.read_settings(ram, found), (SEED, 1, 0, 1))

    def test_notesanity(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block, True))
        self.assert_contract_order(ram, uncommit_first=False)
        self.assertIn(("u8", ram.phys(SETTINGS_AT + 5), 1, 0), ram.writes)
        self.assertEqual(hack.read_settings(ram, found), (SEED, 1, 1, 1))
        ram.writes.clear()
        self.assertFalse(hack.commit(ram, found, SEED, True, self.block, True))
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block, False))     # a change: uncommit first
        self.assert_contract_order(ram, uncommit_first=True)
        self.assertEqual(hack.read_settings(ram, found), (SEED, 1, 0, 1))

    def test_skip_lair_cutscene(self) -> None:
        """The settings' +0x06 (layout 0.12.0): written with the others, before the seed; on unless the slot says."""
        ram = bk_game()
        found = hack.find(ram)
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block))
        self.assertIn(("u8", ram.phys(SETTINGS_AT + 6), 1, 0), ram.writes)
        ram.writes.clear()
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block, skip_lair_cutscene=False))
        self.assert_contract_order(ram, uncommit_first=True)
        self.assertIn(("u8", ram.phys(SETTINGS_AT + 6), 0, 0), ram.writes)
        self.assertEqual(hack.read_settings(ram, found), (SEED, 1, 0, 0))

    def test_nothing_when_held(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        hack.commit(ram, found, SEED, True, self.block)
        ram.writes.clear()
        ram.put(ITEMS_AT + 0x17, b"\x09")           # padding is not compared
        ram.put(ITEMS_AT + 0x25, b"\x09")
        self.assertFalse(hack.commit(ram, found, SEED, True, self.block))
        self.assertEqual(ram.writes, [])

    def test_a_change_uncommits_first(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        hack.commit(ram, found, SEED, True, self.block)
        ram.writes.clear()
        more = hack.items_block(hack.Items(frozenset({0x10, 0x06}), 3, 1, 0, frozenset({1, 2}), frozenset({7})))
        self.assertTrue(hack.commit(ram, found, SEED, True, more))
        self.assert_contract_order(ram, uncommit_first=True)
        self.assertEqual(ram.get(ITEMS_AT, hack.ITEMS_SIZE), more)
        written = {address - ram.phys(ITEMS_AT) for kind, address, *_ in ram.writes if kind == "u8"}
        self.assertEqual(written, {0x06, 0x14, 0x18 + 2, 0x28 + 7}, "only the bytes that differ")

    def test_another_seed_is_replaced(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        hack.commit(ram, found, 0x5EED0001, False, self.block)
        ram.writes.clear()
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block))
        self.assert_contract_order(ram, uncommit_first=True)

    def test_nothing_once_bk_went_away(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        ram.words[hack.ANCHOR] = 0                  # bkbt_return: the switch to Tooie
        self.assertFalse(hack.commit(ram, found, SEED, True, self.block))
        self.assertEqual(ram.writes, [])

    def test_refuses_seed_0(self) -> None:
        ram = bk_game()
        with self.assertRaises(ValueError):
            hack.commit(ram, hack.find(ram), 0, True, self.block)


class TestExits(unittest.TestCase):
    """The exit map (layout 0.13.0): its bytes, its place in the contract's order, and the world's doors."""
    block = hack.items_block(hack.Items(frozenset({0x10})))
    swap = [hack.Exit(0x69, 0x02, 5, 1, 0x07, 4), hack.Exit(0x07, 0x6D, 4, 1, 0x69, 2)]

    def test_block(self) -> None:
        block = hack.exits_block(self.swap + [hack.Exit(0x6D, 0x07, 4, hack.GAME_TOOIE, 0x1AF, 2)])
        self.assertEqual(len(block), hack.EXITS_SIZE)
        self.assertEqual(block[:12], bytes.fromhex("0069 0002 05 01 0007 04 000000"))
        self.assertEqual(block[12:24], bytes.fromhex("0007 006D 04 01 0069 02 000000"))
        self.assertEqual(block[24:36], bytes.fromhex("006D 0007 04 02 01AF 02 000000"))  # a u16 map, another game
        self.assertEqual(block[36:], bytes(hack.EXITS_SIZE - 36), "the rest 0: on_map 0 ends the table")
        self.assertEqual(hack.exits_block([]), bytes(hack.EXITS_SIZE))
        for bad in ([hack.Exit(0, 2, 5, 1, 7, 4)], [hack.Exit(0x69, 2, 0x100, 1, 7, 4)],
                    [hack.Exit(0x69, 2, 5, 1, 0x10000, 4)], self.swap * 17):
            with self.assertRaises(ValueError):
                hack.exits_block(bad)

    def test_written_before_the_seed(self) -> None:
        ram = bk_game()
        found = hack.find(ram)
        exits = hack.exits_block(self.swap)
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block, exits=exits))
        TestCommit.assert_contract_order(self, ram, uncommit_first=False)
        self.assertEqual(ram.get(EXITS_AT, hack.EXITS_SIZE), exits)
        ram.writes.clear()
        self.assertFalse(hack.commit(ram, found, SEED, True, self.block, exits=exits), "nothing when held")
        self.assertEqual(ram.writes, [])
        fewer = hack.exits_block(self.swap[:1])
        self.assertTrue(hack.commit(ram, found, SEED, True, self.block, exits=fewer))   # a change: uncommit first
        TestCommit.assert_contract_order(self, ram, uncommit_first=True)
        written = {address - ram.phys(EXITS_AT) for kind, address, *_ in ram.writes
                   if kind == "u32" and ram.phys(EXITS_AT) <= address < ram.phys(EXITS_AT) + hack.EXITS_SIZE}
        self.assertEqual(written, {12, 16, 20}, "only the words that differ: the second entry's")
        self.assertEqual(ram.get(EXITS_AT, hack.EXITS_SIZE), fewer)

    def test_no_table_by_default(self) -> None:
        ram = bk_game()
        self.assertTrue(hack.commit(ram, hack.find(ram), SEED, True, self.block))
        self.assertFalse(any(EXITS_AT & 0x7FFFFFFF <= address < (EXITS_AT & 0x7FFFFFFF) + hack.EXITS_SIZE
                             for _kind, address, *_ in ram.writes), "an empty table is what every boot starts with")

    def test_exits_of_the_doors(self) -> None:
        self.assertEqual(ids.exits_of(None), [])
        self.assertEqual(ids.exits_of(Entrances.identity()), [])
        swap = Entrances.identity()
        swap["Mumbo's Mountain"], swap["Treasure Trove Cove"] = "Treasure Trove Cove", "Mumbo's Mountain"
        self.assertEqual(ids.exits_of(swap), [
            hack.Exit(0x69, 0x02, 5, 1, 0x07, 4),   # MM's door, in the MM lobby, into TTC at its entrance
            hack.Exit(0x07, 0x6D, 4, 1, 0x69, 2),   # TTC's pad, out to MM's door
            hack.Exit(0x6D, 0x07, 4, 1, 0x02, 5),   # TTC's door, in the TTC lobby, into MM
            hack.Exit(0x02, 0x69, 2, 1, 0x6D, 4),   # MM's pad, out to TTC's door
        ])
        levels = list(Entrances.LEVELS)
        rotated = dict(zip(levels, levels[1:] + levels[:1]))
        exits = ids.exits_of(rotated)
        self.assertEqual(len(exits), 18)
        self.assertEqual(len({(e.on_map, e.og_map, e.og_exit) for e in exits}), 18, "no two entries for one change")
        hack.exits_block(exits)                     # fits
        for bad in ({"Mumbo's Mountain": "Mumbo's Mountain"}, {**Entrances.identity(), "Treasure Trove Cove": "Mumbo's Mountain"}):
            with self.assertRaises(ValueError):
                ids.exits_of(bad)


class TestLink(unittest.TestCase):
    items = hack.Items(frozenset({0x10}), 1, 2, 3, frozenset({1}))

    def test_waits_and_refuses(self) -> None:
        link = hack.Link()
        ram = bk_game()
        ram.words[hack.ANCHOR] = 0
        self.assertEqual(link.tick(ram, SEED, True, self.items).state, "waiting")
        self.assertEqual(link.tick(bk_game(version=(0, 8, 0)), SEED, True, self.items).state, "refused")

    def test_no_seed_writes_nothing(self) -> None:
        ram = bk_game()
        self.assertEqual(hack.Link().tick(ram, None, True, self.items).state, "no seed")
        self.assertEqual(ram.writes, [])

    def test_ready(self) -> None:
        link, ram = hack.Link(), bk_game()
        tick = link.tick(ram, SEED, True, self.items)
        self.assertEqual((tick.state, tick.committed, tick.checks, tick.goal), ("ready", True, frozenset(), False))
        self.assertFalse(link.tick(ram, SEED, True, self.items).committed)
        ram.put(LOCATIONS_AT + 0x30 + 5, b"\x01")
        ram.put(LOCATIONS_AT + GOAL, b"\x01")
        tick = link.tick(ram, SEED, True, self.items)
        self.assertEqual((tick.checks, tick.goal), ({("Jiggy", 5)}, True))
        ram.words[hack.ANCHOR] = 0                  # a switch to Tooie...
        self.assertEqual(link.tick(ram, SEED, True, self.items).state, "waiting")
        ram.words[hack.ANCHOR] = ANCHOR_AT          # ...and back: BK booted again, its settings 0
        ram.put(SETTINGS_AT, bytes(8))
        ram.put(ITEMS_AT, bytes(hack.ITEMS_SIZE))
        self.assertTrue(link.tick(ram, SEED, True, self.items).committed)

    def test_another_seeds_file(self) -> None:
        link, ram = hack.Link(), bk_game()
        found = hack.find(ram)
        hack.commit(ram, found, 0x5EED0001, True, hack.items_block(hack.Items()))
        ram.put(LOCATIONS_AT + 0x30 + 5, b"\x01")   # that file's jiggy
        ram.writes.clear()
        for _ in range(3):
            tick = link.tick(ram, SEED, True, self.items)
            self.assertEqual((tick.state, tick.checks, tick.goal, tick.committed), ("foreign", frozenset(), False, False))
        self.assertEqual(ram.writes, [], "nothing goes into the other seed's file")
        ram.put(LOCATIONS_AT + 0x30 + 5, b"\x00")   # Save and Quit: the file select clears the locations
        tick = link.tick(ram, SEED, True, self.items)
        self.assertEqual((tick.state, tick.committed), ("ready", True))
        self.assertEqual(hack.read_settings(ram, found)[0], SEED)
        ram.put(LOCATIONS_AT + 0x30 + 6, b"\x01")   # a file of this seed
        self.assertEqual(link.tick(ram, SEED, True, self.items).checks, {("Jiggy", 6)})

    def test_back_to_the_files_own_slot(self) -> None:
        # foreign for one slot, then the client connects to the slot the file belongs to: ready at once
        link, ram = hack.Link(), bk_game()
        found = hack.find(ram)
        other = 0x5EED0001
        hack.commit(ram, found, other, True, hack.items_block(hack.Items()))
        ram.put(LOCATIONS_AT + 0x30 + 5, b"\x01")
        self.assertEqual(link.tick(ram, SEED, True, self.items).state, "foreign")
        self.assertEqual(link.tick(ram, None, True, self.items).state, "no seed")     # disconnected
        tick = link.tick(ram, other, True, self.items)                                  # the file's own slot
        self.assertEqual((tick.state, tick.checks), ("ready", {("Jiggy", 5)}))
        self.assertEqual(link.tick(ram, SEED, True, self.items).state, "foreign")     # and away again


class TestLinkDriver(unittest.TestCase):
    """client/link.py against a fake game's link block (include/bkbt.h, BkbtApLink)."""

    def setUp(self) -> None:
        self.ram = bk_game()
        self.found = hack.find(self.ram)
        self.driver = LinkDriver()

    def game(self, **fields) -> None:
        """The game's side: its fields of the block."""
        for name, value in fields.items():
            self.ram.put(LINK_AT + getattr(hack, name.upper() + "_AT"), bytes((value,)))

    def held(self) -> hack.LinkState:
        return hack.read_link(self.ram, self.found)

    def step(self, traps=None) -> Sent:
        return self.driver.step(self.ram, self.found, traps)

    def test_first_look_sends_and_writes_nothing(self) -> None:
        self.game(deaths=2, tags=1)             # before this client saw the game: not sent
        self.assertEqual(self.step(), Sent(0, 0))
        self.assertEqual(self.ram.writes, [])

    def test_own_deaths_and_tags_are_sent(self) -> None:
        self.step()
        self.game(deaths=1)
        self.assertEqual(self.step(), Sent(1, 0))
        self.game(deaths=3, tags=1)
        self.assertEqual(self.step(), Sent(2, 1))
        self.assertEqual(self.step(), Sent(0, 0))
        self.assertEqual(self.ram.writes, [])

    def test_received_are_asked_for_until_applied(self) -> None:
        self.step()
        self.driver.owe(deaths=1, tags=2)
        self.step()
        self.assertEqual(self.held()[:2], (1, 2))
        self.driver.owe(deaths=1)
        self.step()
        self.assertEqual(self.held()[:2], (2, 2))
        self.game(deaths_applied=2, tags_applied=2)
        writes = len(self.ram.writes)
        self.assertEqual(self.step(), Sent(0, 0))
        self.assertEqual(len(self.ram.writes), writes)
        self.assertEqual(self.driver.leave(), (0, 0))

    def test_a_boot_asks_again_for_what_was_not_applied(self) -> None:
        self.step()
        self.driver.owe(deaths=2, tags=1)
        self.step()
        self.game(deaths_applied=1, tags_applied=1)
        self.step()
        self.ram.put(LINK_AT, bytes(hack.LINK_SIZE))    # a reset: the block is 0 again
        self.game(deaths=1)                             # and a death of his own since, which this client did not see
        self.assertEqual(self.step(), Sent(0, 0))
        self.assertEqual(self.held()[:2], (1, 0))      # the death not applied, asked again

    def test_leave_hands_back_what_was_not_applied(self) -> None:
        self.step()
        self.driver.owe(deaths=2, tags=1)
        self.step()
        self.game(deaths_applied=1)
        self.step()
        self.driver.owe(tags=1)                         # received after the last step
        self.assertEqual(self.driver.leave(), (1, 2))
        self.assertEqual(self.driver.describe(), "link: not seen yet")

    def test_traps(self) -> None:
        self.step((0, 2, 0, 0, 1))
        self.assertEqual(self.held().traps, (0, 2, 0, 0, 1))
        self.assertEqual({kind for kind, _at, _value, _seed in self.ram.writes}, {"u8"})
        self.assertEqual(self.ram.get(SETTINGS_AT, 4), bytes(4), "the seed is not touched")
        writes = len(self.ram.writes)
        self.step(None)                                 # not known yet: the game keeps what it holds
        self.step((0, 2, 0, 0, 1))
        self.assertEqual(len(self.ram.writes), writes)
        self.step((0, 2, 1, 0, 1))
        self.assertEqual(self.ram.writes[writes:], [("u8", (LINK_AT + hack.TRAPS_AT + 2) & 0x7FFFFFFF, 1, 0)])

    def test_nothing_once_bk_went_away(self) -> None:
        self.step()
        self.driver.owe(deaths=1)
        self.ram.words[hack.ANCHOR] = 0                 # Tooie took over between find and this step
        self.step((1, 0, 0, 0, 0))
        self.assertEqual(self.ram.writes, [])
        self.assertEqual(self.driver.leave(), (1, 0))


def find_header() -> Optional[Path]:
    """The fork's include/bkbt.h, when the world runs from this repository (not from an installed apworld)."""
    for start in (Path(__file__).resolve(), Path(__file__).absolute()):
        for parent in start.parents:
            header = parent / "hack" / "bk" / "decomp" / "include" / "bkbt.h"
            if header.is_file():
                return header
    return None


HEADER = find_header()


@unittest.skipUnless(HEADER, "the fork's include/bkbt.h is not here")
class TestHeader(unittest.TestCase):
    """hack.py's numbers are the fork's: each struct's field offsets (the /* +0x.. */ comments, which the fork keeps
    as the layout's record), sizes, array lengths and the layout's version."""

    @classmethod
    def setUpClass(cls) -> None:
        text = HEADER.read_text(encoding="utf-8")
        cls.macros = {m.group(1): int(m.group(2), 0) for m in re.finditer(r"#define (BKBT_AP_\w+)\s+(0x[0-9A-Fa-f]+|\d+)\b", text)}
        cls.structs = {}
        for m in re.finditer(r"typedef struct \{([^{}]*)\} (\w+);\s*/\* (\d+) bytes", text):
            fields = {f.group(1): int(f.group(2), 16)
                      for f in re.finditer(r"^\s+\w+ (\w+)(?:\[\w+\])?;\s*/\* \+(0x[0-9A-Fa-f]+)", m.group(1), re.M)}
            cls.structs[m.group(2)] = (int(m.group(3)), fields)

    def test_version(self) -> None:
        self.assertEqual((self.macros["BKBT_AP_VERSION_MAJOR"], self.macros["BKBT_AP_VERSION_MINOR"]), hack.WANT)
        self.assertEqual(self.macros["BKBT_AP_MAGIC"], hack.MAGIC)
        self.assertEqual(self.macros["BKBT_AP_GAME_BK"], hack.GAME_BK)

    def test_settings(self) -> None:
        size, fields = self.structs["BkbtApSettings"]
        self.assertEqual(size, hack.SETTINGS_SIZE)
        self.assertEqual((fields["seed"], fields["skip_intro"], fields["notesanity"], fields["skip_lair_cutscene"]),
                         (hack.SEED_AT, hack.SKIP_INTRO_AT, hack.NOTESANITY_AT, hack.SKIP_LAIR_AT))

    def test_items(self) -> None:
        size, fields = self.structs["BkbtApItems"]
        self.assertEqual(size, hack.ITEMS_SIZE)
        self.assertEqual((fields["moves"], fields["honeycombs"], fields["jiggies"], fields["tokens"], fields["note_doors"],
                          fields["jinjos"], fields["notes"], fields["refills"]),
                         (hack.MOVES_AT, hack.HONEYCOMBS_AT, hack.JIGGIES_AT, hack.TOKENS_AT, hack.NOTE_DOORS_AT,
                          hack.JINJOS_AT, hack.NOTES_AT, hack.REFILLS_AT))
        self.assertEqual(self.macros["BKBT_AP_MOVE_COUNT"], hack.MOVE_COUNT)
        self.assertEqual(self.macros["BKBT_AP_NOTE_DOOR_SLOTS"], hack.NOTE_DOOR_SLOTS)
        self.assertEqual(self.macros["BKBT_AP_JINJO_SLOTS"], hack.JINJO_SLOTS)
        self.assertEqual(self.macros["BKBT_AP_REFILL_KINDS"], hack.REFILL_KINDS)
        self.assertEqual(hack.REFILLS_AT + hack.REFILL_KINDS, hack.ITEMS_SIZE)    # the last field

    def test_locations(self) -> None:
        size, fields = self.structs["BkbtApLocations"]
        self.assertEqual(size, hack.LOCATIONS_SIZE)
        field_of = {"Molehill": "moves", "Honeycomb": "honeycombs", "Jiggy": "jiggies", "Mumbo Token": "tokens",
                    "Note Door": "note_doors", "Jinjo": "jinjos", "Note": "notes"}
        slots_of = {"Molehill": "BKBT_AP_MOVE_COUNT", "Honeycomb": "BKBT_AP_HONEYCOMB_SLOTS",
                    "Jiggy": "BKBT_AP_JIGGY_SLOTS", "Mumbo Token": "BKBT_AP_TOKEN_SLOTS", "Note Door": "BKBT_AP_NOTE_DOOR_SLOTS",
                    "Jinjo": "BKBT_AP_JINJO_SLOTS", "Note": "BKBT_AP_NOTE_SLOTS"}
        for group in hack.GROUPS:
            self.assertEqual(group.at, fields[field_of[group.name]], group.name)
            self.assertEqual(group.slots, self.macros[slots_of[group.name]], group.name)
        self.assertEqual(fields["gruntilda_beaten"], hack.GOAL_AT)
        self.assertEqual([g.name for g in hack.GROUPS if g.bits], ["Note"])
        self.assertEqual(self.macros["BKBT_AP_NOTE_BYTES"] * 8, self.macros["BKBT_AP_NOTE_SLOTS"])

    def test_anchor(self) -> None:
        self.assertEqual(self.structs.get("BkbtApAnchor", (hack.ANCHOR_SIZE,))[0], hack.ANCHOR_SIZE)
        # its pointers, which the field pattern above does not read (a `*`), where find reads them
        text = HEADER.read_text(encoding="utf-8")
        for name, at in (("settings", 0x0C), ("items", 0x10), ("locations", 0x14), ("exits", 0x18), ("link", 0x1C)):
            self.assertRegex(text, rf"\*{name};\s*/\* \+0x{at:02X}:", name)

    def test_exits(self) -> None:
        size, fields = self.structs["BkbtApExit"]
        self.assertEqual(size, hack.EXIT_SIZE)
        self.assertEqual([fields[f] for f in hack.Exit._fields], [0x00, 0x02, 0x04, 0x05, 0x06, 0x08])
        size, fields = self.structs["BkbtApExits"]
        self.assertEqual(size, hack.EXITS_SIZE)
        self.assertEqual((fields["entries"], fields["end"]), (0, hack.EXIT_SLOTS * hack.EXIT_SIZE))
        self.assertEqual(self.macros["BKBT_AP_EXIT_SLOTS"], hack.EXIT_SLOTS)
        self.assertEqual(self.macros["BKBT_AP_GAME_TOOIE"], hack.GAME_TOOIE)

    def test_link(self) -> None:
        size, fields = self.structs["BkbtApLink"]
        self.assertEqual(size, hack.LINK_SIZE)
        names = ("deaths_requested", "tags_requested", "traps", "deaths", "deaths_applied", "tags", "tags_applied",
                 "traps_applied")
        self.assertEqual([fields[n] for n in names], [getattr(hack, n.upper() + "_AT") for n in names])
        self.assertEqual(self.macros["BKBT_AP_TRAP_KINDS"], hack.TRAP_KINDS)
        # the kinds' order, which is Tooie's, is the world's trap items' order (ids.TRAP_OF)
        for kind, name in enumerate(itemName.TRAPS):
            self.assertEqual(self.macros["BKBT_AP_TRAP_" + name.split()[0].upper()], kind, name)
            self.assertEqual(ids.TRAP_OF[name], kind)

    def test_line_references(self) -> None:
        """Every `include/bkbt.h:N` (or `:N-M`) in the client, these tests and the repository's tools cites the line
        that holds what it names: the last BKBT_ macro, Bkbt type or .field named before it in its comment (for a
        range, on one of its lines). The header grows with every feature, and its lines move."""
        header = HEADER.read_text(encoding="utf-8").split("\n")
        world = Path(hack.__file__).resolve().parent.parent
        files = sorted(world.glob("client/*.py")) + [world / "BKClient.py", Path(__file__).resolve()]
        tools = HEADER.parents[4] / "tools"
        files += sorted(tools.glob("*.py")) if tools.is_dir() else []
        ref = re.compile(r"include/bkbt\.h:(\d+)(?:-(\d+))?")
        named = re.compile(r"\bBKBT_[A-Z0-9_]+|\bBkbt[A-Za-z]+|(?<=\.)[a-z_][a-z0-9_]*")
        seen, wrong = 0, []
        for path in files:
            for number, text in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                cursor = text.find("#") + 1     # 0 without a comment: a docstring's line
                for m in ref.finditer(text):
                    seen += 1
                    first, last = int(m.group(1)), int(m.group(2) or m.group(1))
                    names = named.findall(text, cursor, m.start())
                    cursor = m.end()
                    where = f"{path.name}:{number} cites bkbt.h:{m.group(1)}" + (f"-{last}" if m.group(2) else "")
                    if not names:
                        wrong.append(f"{where} and names nothing before it (a BKBT_ macro, a Bkbt type or a .field)")
                        continue
                    name = names[-1]
                    word = re.compile(rf"\b{re.escape(name)}\b")
                    if not (1 <= first <= last <= len(header) and last - first < 40
                            and any(word.search(header[i - 1]) for i in range(first, last + 1))):
                        found = [i for i, line in enumerate(header, 1) if word.search(line)]
                        wrong.append(f"{where} for {name}, which is on line(s) {found or 'none'}")
        self.maxDiff = None
        self.assertEqual(wrong, [])
        self.assertGreaterEqual(seen, 30, "fewer references than hack.py alone holds: the scan missed the client")


class TestPoll(unittest.TestCase):
    """BKClient.poll with the context's network replaced: the checks go out as the world's location ids, each once,
    and the goal as CLIENT_GOAL."""

    def make_context(self):
        from ..BKClient import BanjoKazooieContext
        ctx = BanjoKazooieContext(None, None)
        ctx.slot, ctx.auth, ctx.items_ready = 1, "Banjo", True
        doors = Entrances.identity()
        doors["Mumbo's Mountain"], doors["Treasure Trove Cove"] = "Treasure Trove Cove", "Mumbo's Mountain"
        ctx.slot_data = {"seed": SEED, "skip_intro": True, "notesanity": True, "world_entrances": doors,
                         "layout": [0, 16]}
        ctx.items_received = [NetworkItem(all_item_table[name].bkid, -2, 1, 1)
                              for name in (itemName.TALON_TROT, itemName.JIGGY, itemName.JIGGY, itemName.NOTE_DOORS[0],
                                           MM_BLUE, itemName.NOTE, itemName.NOTE, itemName.NOTE,
                                           itemName.RED_FEATHER_REFILL, itemName.RED_FEATHER_REFILL)]
        ctx.missing_locations = {data.bkid for data in all_location_table.values()}
        ctx.sent_msgs = []

        async def send_msgs(msgs):
            ctx.sent_msgs.extend(msgs)

        ctx.send_msgs = send_msgs
        return ctx

    def run_with_context(self, scenario) -> None:
        """CommonContext starts a task when it is made, so it is made inside the loop the scenario runs in."""
        async def main():
            ctx = self.make_context()
            try:
                await scenario(ctx)
            finally:
                ctx.keep_alive_task.cancel()
        asyncio.run(main())

    def test_poll(self) -> None:
        from ..BKClient import poll

        async def scenario(ctx):
            ram = bk_game()
            tick = await poll(ctx, ram)
            self.assertEqual((tick.state, tick.committed), ("ready", True))
            held = ram.get(ITEMS_AT, hack.ITEMS_SIZE)
            self.assertEqual(held, hack.items_block(hack.Items(frozenset({0x10}), 0, 2, 0, frozenset({1}), frozenset({0}), 3,
                                                               (0, 2, 0, 0))))
            self.assertEqual(held[hack.REFILLS_AT:hack.REFILLS_AT + 4], bytes((0, 2, 0, 0)))  # the two red refills
            self.assertEqual(hack.read_settings(ram, hack.find(ram)), (SEED, 1, 1, 1))   # the slot's notesanity
            self.assertEqual(ram.get(EXITS_AT, hack.EXITS_SIZE),                          # the slot's doors
                             hack.exits_block(ids.exits_of(ctx.slot_data["world_entrances"])))
            self.assertEqual(ctx.sent_msgs, [])
            jiggy = next(data for data in all_location_table.values() if data.group == "Jiggy")
            ram.put(LOCATIONS_AT + 0x30 + jiggy.hack_id, b"\x01")
            ram.put(LOCATIONS_AT + 0x10, b"\x01")       # the Talon Trot molehill
            ram.put(LOCATIONS_AT + JINJOS + 3, b"\x01")  # Mumbo's Mountain's pink Jinjo
            put_note(ram, 205)                          # Clanker's Cavern's note 5
            await poll(ctx, ram)
            await poll(ctx, ram)                        # sent once, not again before the server answers
            self.assertEqual(ctx.sent_msgs, [{"cmd": "LocationChecks", "locations": sorted(
                {jiggy.bkid, all_location_table["MM: Bottles (Talon Trot)"].bkid,
                 all_location_table["MM: Jinjo (Pink)"].bkid, all_location_table[note_name(205)].bkid})}])
            ram.put(LOCATIONS_AT + GOAL, b"\x01")
            await poll(ctx, ram)
            self.assertEqual(ctx.sent_msgs[-1], {"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL})
            self.assertTrue(ctx.finished_game)

        self.run_with_context(scenario)

    def test_link(self) -> None:
        """Deaths and tags received are asked of the game, Banjo's own go out, and the traps received are written."""
        from ..BKClient import poll

        async def scenario(ctx):
            deaths, tags = [], []

            async def send_death(text=""):
                deaths.append(text)

            async def send_tag_link():
                tags.append(True)

            ctx.send_death, ctx.send_tag_link = send_death, send_tag_link
            ctx.tags |= {"DeathLink", "TagLink"}
            ctx.items_received.append(NetworkItem(all_item_table[itemName.TIP_TRAP].bkid, -2, 1, 1))
            ram = bk_game()
            await poll(ctx, ram)
            self.assertEqual(hack.read_link(ram, hack.find(ram))[:3], (0, 0, (0, 0, 0, 0, 1)))
            ctx.on_deathlink({"source": "another player", "time": 1.0})
            ctx.on_package("Bounced", {"tags": ["TagLink"], "data": {"source": 2.0, "tag": True}})
            ctx.on_package("Bounced", {"tags": ["TagLink"], "data": {"source": ctx.instance_id, "tag": True}})
            await poll(ctx, ram)
            self.assertEqual(ram.get(LINK_AT, 2), b"")   # the death and the other's tag, not our own tag
            ram.put(LINK_AT + hack.DEATHS_APPLIED_AT, b"")    # the game applied them
            ram.put(LINK_AT + hack.TAGS_APPLIED_AT, b"")
            ram.put(LINK_AT + hack.DEATHS_AT, b"")            # and Banjo died by himself, and swapped with D-left
            ram.put(LINK_AT + hack.TAGS_AT, b"")
            await poll(ctx, ram)
            self.assertEqual((len(deaths), len(tags)), (1, 1))
            self.assertEqual(ram.get(LINK_AT, 2), b"")   # nothing more asked
            ctx.tags.discard("DeathLink")                          # /deathlink off: his deaths stay his
            ram.put(LINK_AT + hack.DEATHS_AT, b"")
            await poll(ctx, ram)
            self.assertEqual(len(deaths), 1)

        self.run_with_context(scenario)

    def test_waits_for_the_items(self) -> None:
        from ..BKClient import poll

        async def scenario(ctx):
            ram = bk_game()
            ctx.items_ready = False
            ctx.connected_at = float("inf")             # Connected just now, ReceivedItems not in yet
            self.assertEqual((await poll(ctx, ram)).state, "no seed")
            self.assertEqual(ram.writes, [])

        self.run_with_context(scenario)


class TestEmuLoaderPlaces(unittest.TestCase):
    """client/emu.py: the emu_loader package, else the copy this world carries (an installed Archipelago cannot pip
    install), which then answers to the package's name for the stock Tooie client; the copy is EmuLoader 0.1.4
    unchanged and works from a zip; no module imports the package any other way (2026-11-14)."""

    # sha256 of each file of the emu-loader 0.1.4 wheel (its RECORD; git+https://github.com/Killklli/EmuLoader@v0.1.4,
    # commit 61125e5), and of its licenses/LICENSE
    WHEEL = {
        "__init__.py": "3d51d6e408fa49fa31b38d6ea357e997b94802c9a33d70b1abbb73026a9eea07",
        "client.py": "9f478467069eb9788d4a77a4fdf4c2c14ecbe12efeff38c2337ed1e240006b92",
        "emulatorinfo.py": "d9031762a47f5d219f103c3c3e71996ef5bb1901277c77413f5f7e73d3a85d8c",
        "emulators.json": "f1fbea9dffa2b9e29ab1839052e602e73b248c4eacfb7ee8c21e2190cfffcd44",
        "process.py": "cf58d1362a573cf25bd6d41af28cd5ead35a2931cdf031dbb5aee6ae6056121a",
        "ptrace.py": "79ed7c91a928a25f131a282bf34f786f53b1679c210ccf32565d940e66631e2b",
        "retroarch_udp.py": "c108e06e577a59971d6f84fa900ab47c1bc0e7262272707fcc56211773864ebf",
        "utils.py": "9e032aa63539fa92df201212bf4fb7f0d1132ff2e20d179b8c926245beedd9fb",
        "LICENSE": "dd4e0317c8d2daa05fcd0924478375d50a8c342d2b26b06dd01f7585ecb10278",
    }
    COPY = Path(__file__).resolve().parents[1] / "emu_loader"

    def without_the_package(self, replacement=None):
        """sys.modules with no emu_loader (None: an import of it fails), or the replacement, until the test ends."""
        import sys
        saved = {name: module for name, module in sys.modules.items()
                 if name == "emu_loader" or name.startswith("emu_loader.")}

        def restore():
            for name in [n for n in sys.modules if n == "emu_loader" or n.startswith("emu_loader.")]:
                del sys.modules[name]
            sys.modules.update(saved)
        self.addCleanup(restore)
        for name in saved:
            del sys.modules[name]
        sys.modules["emu_loader"] = replacement

    def test_the_package_when_installed(self):
        import types
        from ..client import emu
        package = types.ModuleType("emu_loader")
        self.without_the_package(package)
        self.assertIs(emu.load(), package)

    def test_the_copy_without_the_package(self):
        import sys
        from ..client import emu
        self.without_the_package()
        copy = emu.load()
        self.assertEqual(copy.__name__, "worlds.banjo_kazooie.emu_loader")
        self.assertIs(sys.modules["emu_loader"], copy)
        self.assertIs(sys.modules["emu_loader.client"], copy.client)
        self.assertIs(emu.load(), copy)
        found = {}
        exec("from emu_loader import EmuLoaderClient, ProcessMemory", found)    # as BTClient.py:18
        self.assertIs(found["EmuLoaderClient"], copy.EmuLoaderClient)
        self.assertIs(found["ProcessMemory"], copy.ProcessMemory)

    def test_the_copy_is_emu_loader_0_1_4_unchanged(self):
        import hashlib
        shipped = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.COPY.iterdir()
                   if p.is_file() and p.name != "README.md"}
        self.assertEqual(shipped, self.WHEEL)
        self.assertIn("MIT License", (self.COPY / "LICENSE").read_text(encoding="utf-8"))

    def test_the_copy_reads_its_emulators_inside_a_zip(self):
        # as inside the apworld: importlib.resources from a zipimport, in a Python of its own that has no Archipelago
        import subprocess
        import sys
        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "world.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("pkg/__init__.py", "")
                for name in self.WHEEL:
                    z.write(self.COPY / name, f"pkg/emu_loader/{name}")
            code = ("import sys; sys.path.insert(0, sys.argv[1]); import pkg.emu_loader as e; "
                    "assert '.zip' in e.__file__, e.__file__; "
                    "print(sorted(e.load_emulator_configs(pull_from_web=False)))")
            run = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(archive)], capture_output=True,
                                 text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("'Project64'", run.stdout)

    def test_no_module_imports_the_package_itself(self):
        worlds = Path(__file__).resolve().parents[2]
        found = []
        for world in ("banjo_kazooie", "banjo_kazooie_tooie"):
            for path in (worlds / world).rglob("*.py"):
                parts = path.relative_to(worlds / world).parts
                if "test" in parts or "emu_loader" in parts or path.name == "emu.py":
                    continue
                if re.search(r"^\s*(from emu_loader import|import emu_loader)", path.read_text(encoding="utf-8"), re.M):
                    found.append(str(path.relative_to(worlds)))
        self.assertEqual(found, [], "import it through client/emu.py's load (or the stock BTClient's EmuLoaderClient)")
