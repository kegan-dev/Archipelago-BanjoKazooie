"""Deaths, tags and traps between Banjo-Kazooie and the multiworld while BK runs: the client's side of the hack's link
block (client/hack.py, read_link and write_link; hack/bk/decomp/include/bkbt.h, BkbtApLink).

The game counts Banjo's own deaths and the forms he changes with D-pad left, each this boot; the client sends them.
The client asks the game for deaths and tags it has received, as running totals this boot that the game applies when
it can, and writes the traps of each kind given to this game, which the game plays while the counts saved with its
file are below. Both clients use this for BK: BKClient.py, and the Banjo-Kazooie & Tooie client while BK runs, which
hands back what BK did not apply when Tooie takes over (`leave`).

Pure Python, so that the tests and tools can load it by path.
"""

from typing import Iterable, NamedTuple, Optional, Tuple

from . import hack


class Sent(NamedTuple):
    """What the game did by itself since the last step: its own deaths and tags, for the client to send."""
    deaths: int = 0
    tags: int = 0


class LinkDriver:
    """The link, one step per poll while BK plays with the seed committed (hack.Tick "ready")."""

    def __init__(self) -> None:
        self.deaths_owed = 0    # received, not yet given to the game
        self.tags_owed = 0
        self.last: Optional[hack.LinkState] = None  # the block as read at the last step, this boot
        self.anchor: Optional[int] = None
        self.written: Optional[Tuple[int, int]] = None  # the deaths and tags requested this client last wrote

    def owe(self, deaths: int = 0, tags: int = 0) -> None:
        """Deaths and tags received, for the game."""
        self.deaths_owed += deaths
        self.tags_owed += tags

    def _unapplied(self) -> Tuple[int, int]:
        if self.last is None or self.written is None:
            return 0, 0
        return ((self.written[0] - self.last.deaths_applied) & 0xFF, (self.written[1] - self.last.tags_applied) & 0xFF)

    def leave(self) -> Tuple[int, int]:
        """BK stopped (the other game took over): the deaths and tags received that it did not apply, handed back
        for whichever game runs next, and the state forgotten."""
        deaths, tags = self._unapplied()
        deaths += self.deaths_owed
        tags += self.tags_owed
        self.__init__()
        return deaths, tags

    def step(self, mem, found: "hack.Found", traps: Optional[Iterable[int]] = None) -> Sent:
        """Read the link, give the game what is owed and `traps` (the totals of each kind given to this game; None:
        not known yet, nothing written), and return what it did by itself."""
        state = hack.read_link(mem, found)
        if found.anchor != self.anchor or self.written is None or \
                (state.deaths_requested, state.tags_requested) != self.written:
            # A boot this driver has not seen (the first look, another build, or a reset: the game's block is 0
            # again): what the last boot did not apply is owed again, and the game's counts so far are not sent,
            # since this client did not see them happen.
            deaths, tags = self._unapplied()
            self.owe(deaths, tags)
            self.anchor = found.anchor
            self.written = (state.deaths_requested, state.tags_requested)
            self.last = state
        sent = Sent((state.deaths - self.last.deaths) & 0xFF, (state.tags - self.last.tags) & 0xFF)
        deaths_requested = (self.written[0] + self.deaths_owed) & 0xFF
        tags_requested = (self.written[1] + self.tags_owed) & 0xFF
        held_traps = state.traps
        traps = tuple(traps) if traps is not None else held_traps
        if hack.write_link(mem, found, state, deaths_requested, tags_requested, traps):
            self.written = (deaths_requested, tags_requested)
            self.deaths_owed = self.tags_owed = 0
            state = state._replace(deaths_requested=deaths_requested, tags_requested=tags_requested, traps=traps)
        elif (deaths_requested, tags_requested) == self.written:
            self.deaths_owed = self.tags_owed = 0
        self.last = state
        return sent

    def describe(self) -> str:
        """For the clients' /bk."""
        if self.last is None:
            return "link: not seen yet"
        s = self.last
        return (f"link: deaths {s.deaths} own, {s.deaths_applied}/{s.deaths_requested} received applied; tags {s.tags} "
                f"own, {s.tags_applied}/{s.tags_requested} applied; traps {list(s.traps_applied)} of {list(s.traps)}")
