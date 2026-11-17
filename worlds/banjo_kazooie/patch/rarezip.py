"""Rare's compression of Banjo-Kazooie's code, in pure Python: gzip 1.2.4's deflate as the decomp's rarezip runs it.

Banjo-Kazooie stores each overlay's code and data as `11 72`, the uncompressed length as a big-endian u32, and a raw
deflate stream. The decomp reproduces Rare's bytes with gzip 1.2.4 itself (hack/bk/decomp/tools/bk_rom_compressor/
rarezip/gzip, `bk_zip` in zip.c:184-208), and the build links each compressed segment's ROM offset into the code, so a
ROM made from the player's retail ROM has to compress to the same bytes: Python's zlib does not (measured on retail's
30 streams, 2026-11-09). This is that gzip, ported function for function at the level rarezip runs it, 6 (gzip.c:217):
deflate.c's lazy `_deflate`, `longest_match`, `fill_window` and `lm_init`, trees.c's `ct_tally`, `flush_block` and
the trees, bits.c's bit output. Comments name the C each part follows (paths in that gzip directory).

Two things keep the output identical: the window is the C's own 64 KiB buffer, slid the same way, because a match
near the end of the input reads bytes past it (deflate.c:404-430) and those are whatever the window held; and every
choice the C makes on a tie (the heap's `smaller`, trees.c) is made the same. Faster than a literal port only where
the result cannot differ: a match's length is found by comparing 255 bytes at once.
"""

from typing import List, Optional

__all__ = ["deflate", "bk_zip", "bk_unzip"]

# deflate.c, gzip.h
WSIZE = 0x8000
WMASK = WSIZE - 1
WINDOW_SIZE = 2 * WSIZE
HASH_BITS = 15
HASH_SIZE = 1 << HASH_BITS
HASH_MASK = HASH_SIZE - 1
H_SHIFT = (HASH_BITS + 3 - 1) // 3          # 5
MIN_MATCH = 3
MAX_MATCH = 258
MIN_LOOKAHEAD = MAX_MATCH + MIN_MATCH + 1   # 262
MAX_DIST = WSIZE - MIN_LOOKAHEAD
TOO_FAR = 4096
LEVEL = 6
# configuration_table[6] (deflate.c:234): good, lazy, nice, chain
GOOD_MATCH, MAX_LAZY_MATCH, NICE_MATCH, MAX_CHAIN_LENGTH = 8, 16, 128, 128

# trees.c
LIT_BUFSIZE = DIST_BUFSIZE = 0x8000
MAX_BITS = 15
MAX_BL_BITS = 7
LENGTH_CODES = 29
LITERALS = 256
END_BLOCK = 256
L_CODES = LITERALS + 1 + LENGTH_CODES       # 286
D_CODES = 30
BL_CODES = 19
HEAP_SIZE = 2 * L_CODES + 1                 # 573
REP_3_6, REPZ_3_10, REPZ_11_138 = 16, 17, 18
STORED_BLOCK, STATIC_TREES, DYN_TREES = 0, 1, 2
EXTRA_LBITS = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
EXTRA_DBITS = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)
EXTRA_BLBITS = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3, 7)
BL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


def _bi_reverse(code: int, length: int) -> int:
    """bits.c, bi_reverse."""
    res = 0
    while True:
        res |= code & 1
        code >>= 1
        res <<= 1
        length -= 1
        if length <= 0:
            return res >> 1


def _gen_codes(lens: List[int], codes: List[int], max_code: int, bl_count: List[int]) -> None:
    """trees.c, gen_codes: the codes of a tree from its bit lengths (written over the frequencies, as the C's union)."""
    next_code = [0] * (MAX_BITS + 1)
    code = 0
    for bits in range(1, MAX_BITS + 1):
        code = ((code + bl_count[bits - 1]) << 1) & 0xFFFF
        next_code[bits] = code
    for n in range(max_code + 1):
        length = lens[n]
        if length == 0:
            continue
        codes[n] = _bi_reverse(next_code[length], length)
        next_code[length] += 1


# ct_init's tables (trees.c), the same for every call
LENGTH_CODE = [0] * (MAX_MATCH - MIN_MATCH + 1)
BASE_LENGTH = [0] * LENGTH_CODES
DIST_CODE = [0] * 512
BASE_DIST = [0] * D_CODES


def _init_tables():
    length = 0
    for code in range(LENGTH_CODES - 1):
        BASE_LENGTH[code] = length
        for _ in range(1 << EXTRA_LBITS[code]):
            LENGTH_CODE[length] = code
            length += 1
    # the length 255 (match length 258) is code 285, not 284 + 5 bits; base_length[28] stays 0
    LENGTH_CODE[length - 1] = LENGTH_CODES - 1
    dist = 0
    for code in range(16):
        BASE_DIST[code] = dist
        for _ in range(1 << EXTRA_DBITS[code]):
            DIST_CODE[dist] = code
            dist += 1
    dist >>= 7
    for code in range(16, D_CODES):
        BASE_DIST[code] = dist << 7
        for _ in range(1 << (EXTRA_DBITS[code] - 7)):
            DIST_CODE[256 + dist] = code
            dist += 1
    lens = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
    bl_count = [0] * (MAX_BITS + 1)
    for length in lens:
        bl_count[length] += 1
    codes = [0] * (L_CODES + 2)
    _gen_codes(lens, codes, L_CODES + 1, bl_count)
    return lens, codes, [5] * D_CODES, [_bi_reverse(n, 5) for n in range(D_CODES)]


_init_tables_result = _init_tables()
STATIC_LLEN, STATIC_LCODE, STATIC_DLEN, STATIC_DCODE = _init_tables_result


class _Tree:
    """trees.c's ct_data array and tree_desc: `fc` is the union of Freq and Code, `dl` of Dad and Len."""
    __slots__ = ("fc", "dl", "slen", "extra", "base", "elems", "max_length", "max_code")

    def __init__(self, size, slen, extra, base, elems, max_length):
        self.fc = [0] * size
        self.dl = [0] * size
        self.slen = slen
        self.extra, self.base, self.elems, self.max_length = extra, base, elems, max_length
        self.max_code = 0


class _Trees:
    """trees.c and bits.c: the trees, the tallies, the blocks and the bits, for one compression."""

    def __init__(self, out: bytearray):
        self.out = out
        self.bi_buf = 0
        self.bi_valid = 0
        self.l = _Tree(HEAP_SIZE, STATIC_LLEN, EXTRA_LBITS, LITERALS + 1, L_CODES, MAX_BITS)
        self.d = _Tree(2 * D_CODES + 1, STATIC_DLEN, EXTRA_DBITS, 0, D_CODES, MAX_BITS)
        self.bl = _Tree(2 * BL_CODES + 1, None, EXTRA_BLBITS, 0, BL_CODES, MAX_BL_BITS)
        self.heap = [0] * HEAP_SIZE
        self.heap_len = 0
        self.heap_max = 0
        self.depth = [0] * HEAP_SIZE
        self.bl_count = [0] * (MAX_BITS + 1)
        self.opt_len = 0
        self.static_len = 0
        self.init_block()

    # -- bits.c --------------------------------------------------------------------------------------------

    def send_bits(self, value: int, length: int) -> None:
        bi_valid = self.bi_valid
        if bi_valid > 16 - length:
            buf = (self.bi_buf | (value << bi_valid)) & 0xFFFF
            self.out.append(buf & 0xFF)
            self.out.append(buf >> 8)
            self.bi_buf = (value & 0xFFFF) >> (16 - bi_valid)
            self.bi_valid = bi_valid + length - 16
        else:
            self.bi_buf = (self.bi_buf | (value << bi_valid)) & 0xFFFF
            self.bi_valid = bi_valid + length

    def bi_windup(self) -> None:
        if self.bi_valid > 8:
            self.out.append(self.bi_buf & 0xFF)
            self.out.append(self.bi_buf >> 8)
        elif self.bi_valid > 0:
            self.out.append(self.bi_buf & 0xFF)
        self.bi_buf = 0
        self.bi_valid = 0

    def copy_block(self, data, length: int, header: bool) -> None:
        self.bi_windup()
        if header:
            self.out += bytes((length & 0xFF, (length >> 8) & 0xFF, ~length & 0xFF, (~length >> 8) & 0xFF))
        self.out += data

    # -- trees.c -------------------------------------------------------------------------------------------

    def init_block(self) -> None:
        for tree, n in ((self.l, L_CODES), (self.d, D_CODES), (self.bl, BL_CODES)):
            fc = tree.fc
            for i in range(n):
                fc[i] = 0
        self.l.fc[END_BLOCK] = 1
        self.opt_len = self.static_len = 0

    def pqdownheap(self, tree: _Tree, k: int) -> None:
        heap, depth, fc, heap_len = self.heap, self.depth, tree.fc, self.heap_len
        v = heap[k]
        j = k << 1
        while j <= heap_len:
            if j < heap_len:
                a, b = heap[j + 1], heap[j]
                if fc[a] < fc[b] or (fc[a] == fc[b] and depth[a] <= depth[b]):
                    j += 1
            hj = heap[j]
            if fc[v] < fc[hj] or (fc[v] == fc[hj] and depth[v] <= depth[hj]):
                break
            heap[k] = hj
            k = j
            j <<= 1
        heap[k] = v

    def gen_bitlen(self, tree: _Tree) -> None:
        fc, dl, extra, base = tree.fc, tree.dl, tree.extra, tree.base
        max_code, max_length, slen = tree.max_code, tree.max_length, tree.slen
        heap, bl_count = self.heap, self.bl_count
        for bits in range(MAX_BITS + 1):
            bl_count[bits] = 0
        dl[heap[self.heap_max]] = 0
        overflow = 0
        opt_len, static_len = self.opt_len, self.static_len
        for h in range(self.heap_max + 1, HEAP_SIZE):
            n = heap[h]
            bits = dl[dl[n]] + 1
            if bits > max_length:
                bits = max_length
                overflow += 1
            dl[n] = bits
            if n > max_code:
                continue
            bl_count[bits] += 1
            xbits = extra[n - base] if n >= base else 0
            f = fc[n]
            opt_len += f * (bits + xbits)
            if slen is not None:
                static_len += f * (slen[n] + xbits)
        if overflow != 0:
            while True:
                bits = max_length - 1
                while bl_count[bits] == 0:
                    bits -= 1
                bl_count[bits] -= 1
                bl_count[bits + 1] += 2
                bl_count[max_length] -= 1
                overflow -= 2
                if overflow <= 0:
                    break
            h = HEAP_SIZE
            for bits in range(max_length, 0, -1):
                n = bl_count[bits]
                while n != 0:
                    h -= 1
                    m = heap[h]
                    if m > max_code:
                        continue
                    if dl[m] != bits:
                        opt_len += (bits - dl[m]) * fc[m]
                        dl[m] = bits
                    n -= 1
        self.opt_len, self.static_len = opt_len, static_len

    def build_tree(self, tree: _Tree) -> None:
        fc, dl, slen, elems = tree.fc, tree.dl, tree.slen, tree.elems
        heap, depth = self.heap, self.depth
        max_code = -1
        heap_len = 0
        self.heap_max = HEAP_SIZE
        for n in range(elems):
            if fc[n] != 0:
                heap_len += 1
                heap[heap_len] = max_code = n
                depth[n] = 0
            else:
                dl[n] = 0
        while heap_len < 2:
            if max_code < 2:
                max_code += 1
                new = max_code
            else:
                new = 0
            heap_len += 1
            heap[heap_len] = new
            fc[new] = 1
            depth[new] = 0
            self.opt_len -= 1
            if slen is not None:
                self.static_len -= slen[new]
        tree.max_code = max_code
        self.heap_len = heap_len
        for n in range(heap_len // 2, 0, -1):
            self.pqdownheap(tree, n)
        node = elems
        while True:
            n = heap[1]
            heap[1] = heap[self.heap_len]
            self.heap_len -= 1
            self.pqdownheap(tree, 1)
            m = heap[1]
            self.heap_max -= 1
            heap[self.heap_max] = n
            self.heap_max -= 1
            heap[self.heap_max] = m
            fc[node] = (fc[n] + fc[m]) & 0xFFFF
            depth[node] = ((depth[n] if depth[n] >= depth[m] else depth[m]) + 1) & 0xFF
            dl[n] = dl[m] = node
            heap[1] = node
            node += 1
            self.pqdownheap(tree, 1)
            if self.heap_len < 2:
                break
        self.heap_max -= 1
        heap[self.heap_max] = heap[1]
        self.gen_bitlen(tree)
        _gen_codes(dl, fc, max_code, self.bl_count)

    def scan_tree(self, tree: _Tree, max_code: int) -> None:
        dl = tree.dl
        blf = self.bl.fc
        prevlen = -1
        nextlen = dl[0]
        count = 0
        max_count, min_count = 7, 4
        if nextlen == 0:
            max_count, min_count = 138, 3
        dl[max_code + 1] = 0xFFFF
        for n in range(max_code + 1):
            curlen = nextlen
            nextlen = dl[n + 1]
            count += 1
            if count < max_count and curlen == nextlen:
                continue
            elif count < min_count:
                blf[curlen] += count
            elif curlen != 0:
                if curlen != prevlen:
                    blf[curlen] += 1
                blf[REP_3_6] += 1
            elif count <= 10:
                blf[REPZ_3_10] += 1
            else:
                blf[REPZ_11_138] += 1
            count = 0
            prevlen = curlen
            if nextlen == 0:
                max_count, min_count = 138, 3
            elif curlen == nextlen:
                max_count, min_count = 6, 3
            else:
                max_count, min_count = 7, 4

    def send_tree(self, tree: _Tree, max_code: int) -> None:
        dl = tree.dl
        bcode, blen = self.bl.fc, self.bl.dl
        send_bits = self.send_bits
        prevlen = -1
        nextlen = dl[0]
        count = 0
        max_count, min_count = 7, 4
        if nextlen == 0:
            max_count, min_count = 138, 3
        for n in range(max_code + 1):
            curlen = nextlen
            nextlen = dl[n + 1]
            count += 1
            if count < max_count and curlen == nextlen:
                continue
            elif count < min_count:
                while True:
                    send_bits(bcode[curlen], blen[curlen])
                    count -= 1
                    if count == 0:
                        break
            elif curlen != 0:
                if curlen != prevlen:
                    send_bits(bcode[curlen], blen[curlen])
                    count -= 1
                send_bits(bcode[REP_3_6], blen[REP_3_6])
                send_bits(count - 3, 2)
            elif count <= 10:
                send_bits(bcode[REPZ_3_10], blen[REPZ_3_10])
                send_bits(count - 3, 3)
            else:
                send_bits(bcode[REPZ_11_138], blen[REPZ_11_138])
                send_bits(count - 11, 7)
            count = 0
            prevlen = curlen
            if nextlen == 0:
                max_count, min_count = 138, 3
            elif curlen == nextlen:
                max_count, min_count = 6, 3
            else:
                max_count, min_count = 7, 4

    def build_bl_tree(self) -> int:
        self.scan_tree(self.l, self.l.max_code)
        self.scan_tree(self.d, self.d.max_code)
        self.build_tree(self.bl)
        blen = self.bl.dl
        max_blindex = BL_CODES - 1
        while max_blindex >= 3:
            if blen[BL_ORDER[max_blindex]] != 0:
                break
            max_blindex -= 1
        self.opt_len += 3 * (max_blindex + 1) + 5 + 5 + 4
        return max_blindex

    def send_all_trees(self, lcodes: int, dcodes: int, blcodes: int) -> None:
        self.send_bits(lcodes - 257, 5)
        self.send_bits(dcodes - 1, 5)
        self.send_bits(blcodes - 4, 4)
        blen = self.bl.dl
        for rank in range(blcodes):
            self.send_bits(blen[BL_ORDER[rank]], 3)
        self.send_tree(self.l, lcodes - 1)
        self.send_tree(self.d, dcodes - 1)

    def compress_block(self, lcode, llen, dcode, dlen, l_buf, d_buf, flag_buf, last_lit) -> None:
        send_bits = self.send_bits
        lx = dx = fx = 0
        flag = 0
        if last_lit != 0:
            while True:
                if (lx & 7) == 0:
                    flag = flag_buf[fx]
                    fx += 1
                lc = l_buf[lx]
                lx += 1
                if (flag & 1) == 0:
                    send_bits(lcode[lc], llen[lc])
                else:
                    code = LENGTH_CODE[lc]
                    send_bits(lcode[code + LITERALS + 1], llen[code + LITERALS + 1])
                    extra = EXTRA_LBITS[code]
                    if extra != 0:
                        send_bits(lc - BASE_LENGTH[code], extra)
                    dist = d_buf[dx]
                    dx += 1
                    code = DIST_CODE[dist] if dist < 256 else DIST_CODE[256 + (dist >> 7)]
                    send_bits(dcode[code], dlen[code])
                    extra = EXTRA_DBITS[code]
                    if extra != 0:
                        send_bits(dist - BASE_DIST[code], extra)
                flag >>= 1
                if lx >= last_lit:
                    break
        send_bits(lcode[END_BLOCK], llen[END_BLOCK])

    def flush_block(self, data, stored_len: int, eof: int, l_buf, d_buf, flag_buf, last_lit, last_flags,
                    flags) -> None:
        """trees.c, flush_block, with seekable() 0 (gzip.h:237): `data` is the block's bytes, or None when the
        block's start has left the window (the C's NULL buf)."""
        flag_buf[last_flags] = flags
        self.build_tree(self.l)
        self.build_tree(self.d)
        max_blindex = self.build_bl_tree()
        opt_lenb = (self.opt_len + 3 + 7) >> 3
        static_lenb = (self.static_len + 3 + 7) >> 3
        if static_lenb <= opt_lenb:
            opt_lenb = static_lenb
        if stored_len + 4 <= opt_lenb and data is not None:
            self.send_bits((STORED_BLOCK << 1) + eof, 3)
            self.copy_block(data, stored_len, True)
        elif static_lenb == opt_lenb:
            self.send_bits((STATIC_TREES << 1) + eof, 3)
            self.compress_block(STATIC_LCODE, STATIC_LLEN, STATIC_DCODE, STATIC_DLEN, l_buf, d_buf, flag_buf,
                                last_lit)
        else:
            self.send_bits((DYN_TREES << 1) + eof, 3)
            self.send_all_trees(self.l.max_code + 1, self.d.max_code + 1, max_blindex + 1)
            self.compress_block(self.l.fc, self.l.dl, self.d.fc, self.d.dl, l_buf, d_buf, flag_buf, last_lit)
        self.init_block()
        if eof:
            self.bi_windup()


def deflate(data: bytes) -> bytes:
    """A raw deflate stream of `data`, as gzip 1.2.4 at level 6 writes it (rarezip's `deflate`, zip.c:103-118)."""
    out = bytearray()
    trees = _Trees(out)
    lfreq, dfreq = trees.l.fc, trees.d.fc
    src = memoryview(bytes(data))
    src_len = len(src)
    src_pos = 0

    # bufs_init (zip.c:210-225) and lm_init (deflate.c:290-343)
    window = bytearray(WINDOW_SIZE)
    head = [0] * HASH_SIZE
    prev = [0] * WSIZE
    l_buf = bytearray(LIT_BUFSIZE)
    d_buf = [0] * DIST_BUFSIZE
    flag_buf = bytearray(LIT_BUFSIZE // 8)
    last_lit = last_dist = last_flags = 0
    flags = 0
    flag_bit = 1

    strstart = 0
    block_start = 0
    match_start = 0
    n = min(WINDOW_SIZE, src_len)
    window[0:n] = src[0:n]
    src_pos = n
    lookahead = n
    eofile = 0
    if lookahead == 0:
        eofile = 1
    ins_h = 0
    if lookahead:
        # fill_window cannot read more here: the window is full or the input is all in it
        if src_pos >= src_len and lookahead < MIN_LOOKAHEAD:
            eofile = 1
        for j in range(MIN_MATCH - 1):
            ins_h = ((ins_h << H_SHIFT) ^ window[j]) & HASH_MASK

    # _deflate (deflate.c:665-768), with ct_tally (trees.c:1029-1063) inline
    prev_length = MIN_MATCH - 1
    match_available = 0
    match_length = MIN_MATCH - 1
    from_bytes = int.from_bytes
    flush_block = trees.flush_block
    while lookahead != 0:
        # INSERT_STRING(strstart, hash_head)
        ins_h = ((ins_h << H_SHIFT) ^ window[strstart + MIN_MATCH - 1]) & HASH_MASK
        hash_head = head[ins_h]
        prev[strstart & WMASK] = hash_head
        head[ins_h] = strstart

        prev_length = match_length
        prev_match = match_start
        match_length = MIN_MATCH - 1

        if hash_head != 0 and prev_length < MAX_LAZY_MATCH and strstart - hash_head <= MAX_DIST:
            # longest_match(hash_head) (deflate.c:355-468), the C without UNALIGNED_OK
            cur_match = hash_head
            chain_length = MAX_CHAIN_LENGTH
            scan = strstart
            best_len = prev_length
            limit = strstart - MAX_DIST if strstart > MAX_DIST else 0
            scan_end1 = window[scan + best_len - 1]
            scan_end = window[scan + best_len]
            s0 = window[scan]
            s1 = window[scan + 1]
            scan_int = None
            if prev_length >= GOOD_MATCH:
                chain_length >>= 2
            while True:
                if (window[cur_match + best_len] == scan_end and window[cur_match + best_len - 1] == scan_end1
                        and window[cur_match] == s0 and window[cur_match + 1] == s1):
                    # bytes 3..257 compared; byte 2 is equal by the hash (deflate.c:418-430)
                    if scan_int is None:
                        scan_int = from_bytes(window[scan + 3:scan + MAX_MATCH], "big")
                    x = scan_int ^ from_bytes(window[cur_match + 3:cur_match + MAX_MATCH], "big")
                    length = MAX_MATCH if x == 0 else 3 + ((2040 - x.bit_length()) >> 3)
                    if length > best_len:
                        match_start = cur_match
                        best_len = length
                        if length >= NICE_MATCH:
                            break
                        scan_end1 = window[scan + best_len - 1]
                        scan_end = window[scan + best_len]
                cur_match = prev[cur_match & WMASK]
                if cur_match <= limit:
                    break
                chain_length -= 1
                if chain_length == 0:
                    break
            match_length = best_len
            if match_length > lookahead:
                match_length = lookahead
            if match_length == MIN_MATCH and strstart - match_start > TOO_FAR:
                match_length -= 1

        if prev_length >= MIN_MATCH and match_length <= prev_length:
            # ct_tally(strstart-1-prev_match, prev_length-MIN_MATCH)
            dist = strstart - 1 - prev_match
            lc = prev_length - MIN_MATCH
            l_buf[last_lit] = lc
            last_lit += 1
            dist -= 1
            lfreq[LENGTH_CODE[lc] + LITERALS + 1] += 1
            dfreq[DIST_CODE[dist] if dist < 256 else DIST_CODE[256 + (dist >> 7)]] += 1
            d_buf[last_dist] = dist
            last_dist += 1
            flags |= flag_bit
            flag_bit = (flag_bit << 1) & 0xFF
            if (last_lit & 7) == 0:
                flag_buf[last_flags] = flags
                last_flags += 1
                flags = 0
                flag_bit = 1
            do_flush = last_lit == LIT_BUFSIZE - 1 or last_dist == DIST_BUFSIZE
            if (last_lit & 0xFFF) == 0:
                out_length = last_lit * 8
                in_length = strstart - block_start
                for dcode in range(D_CODES):
                    out_length += dfreq[dcode] * (5 + EXTRA_DBITS[dcode])
                out_length >>= 3
                if last_dist < last_lit // 2 and out_length < in_length // 2:
                    do_flush = True

            lookahead -= prev_length - 1
            prev_length -= 2
            while True:
                strstart += 1
                ins_h = ((ins_h << H_SHIFT) ^ window[strstart + MIN_MATCH - 1]) & HASH_MASK
                hash_head = head[ins_h]
                prev[strstart & WMASK] = hash_head
                head[ins_h] = strstart
                prev_length -= 1
                if prev_length == 0:
                    break
            match_available = 0
            match_length = MIN_MATCH - 1
            strstart += 1
            if do_flush:
                flush_block(bytes(window[block_start:strstart]) if block_start >= 0 else None,
                            strstart - block_start, 0, l_buf, d_buf, flag_buf, last_lit, last_flags, flags)
                last_lit = last_dist = last_flags = 0
                flags = 0
                flag_bit = 1
                block_start = strstart
        elif match_available:
            # ct_tally(0, window[strstart-1])
            lc = window[strstart - 1]
            l_buf[last_lit] = lc
            last_lit += 1
            lfreq[lc] += 1
            flag_bit = (flag_bit << 1) & 0xFF
            if (last_lit & 7) == 0:
                flag_buf[last_flags] = flags
                last_flags += 1
                flags = 0
                flag_bit = 1
            do_flush = last_lit == LIT_BUFSIZE - 1 or last_dist == DIST_BUFSIZE
            if (last_lit & 0xFFF) == 0:
                out_length = last_lit * 8
                in_length = strstart - block_start
                for dcode in range(D_CODES):
                    out_length += dfreq[dcode] * (5 + EXTRA_DBITS[dcode])
                out_length >>= 3
                if last_dist < last_lit // 2 and out_length < in_length // 2:
                    do_flush = True
            if do_flush:
                flush_block(bytes(window[block_start:strstart]) if block_start >= 0 else None,
                            strstart - block_start, 0, l_buf, d_buf, flag_buf, last_lit, last_flags, flags)
                last_lit = last_dist = last_flags = 0
                flags = 0
                flag_bit = 1
                block_start = strstart
            strstart += 1
            lookahead -= 1
        else:
            match_available = 1
            strstart += 1
            lookahead -= 1

        # while (lookahead < MIN_LOOKAHEAD && !eofile) fill_window(); (deflate.c:525-566)
        while lookahead < MIN_LOOKAHEAD and not eofile:
            more = WINDOW_SIZE - lookahead - strstart
            if strstart >= WSIZE + MAX_DIST:
                window[0:WSIZE] = window[WSIZE:WINDOW_SIZE]
                match_start -= WSIZE
                strstart -= WSIZE
                block_start -= WSIZE
                head = [m - WSIZE if m >= WSIZE else 0 for m in head]
                prev = [m - WSIZE if m >= WSIZE else 0 for m in prev]
                more += WSIZE
            n = min(more, src_len - src_pos)
            if n == 0:
                eofile = 1
            else:
                at = strstart + lookahead
                window[at:at + n] = src[src_pos:src_pos + n]
                src_pos += n
                lookahead += n

    if match_available:
        lc = window[strstart - 1]
        l_buf[last_lit] = lc
        last_lit += 1
        lfreq[lc] += 1
        flag_bit = (flag_bit << 1) & 0xFF
        if (last_lit & 7) == 0:
            flag_buf[last_flags] = flags
            last_flags += 1
            flags = 0
            flag_bit = 1
    flush_block(bytes(window[block_start:strstart]) if block_start >= 0 else None, strstart - block_start, 1,
                l_buf, d_buf, flag_buf, last_lit, last_flags, flags)
    return bytes(out)


def bk_zip(data: bytes) -> bytes:
    """Banjo-Kazooie's compressed form of `data`: `11 72`, its length as a big-endian u32, the raw deflate stream
    (rarezip's bk_zip, zip.c:184-208)."""
    return b"\x11\x72" + len(data).to_bytes(4, "big") + deflate(data)


def bk_unzip(data: bytes) -> bytes:
    """`data` uncompressed from Banjo-Kazooie's compressed form; trailing bytes after the stream are ignored."""
    import zlib
    if data[:2] != b"\x11\x72":
        raise ValueError("not a Banjo-Kazooie compressed stream (no 11 72)")
    size = int.from_bytes(data[2:6], "big")
    out = zlib.decompressobj(-15).decompress(data[6:])
    if len(out) != size:
        raise ValueError(f"the stream inflates to {len(out)} bytes, not {size}")
    return out
