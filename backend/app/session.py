"""Blind test session state machine.

A session = N rounds. Each round picks one song, runs a timed window (default
30s) with two hint reveals (t=10s: year, t=20s: artist+title initials), and
ends either on timeout or when one player has matched BOTH artist and title.
On full match, the round shortens to at most `short_finish_seconds`.

Scoring : +1 for matching the artist, +1 for the title, +1 bonus to the
first player who matches both. Each (player, round) credits each component
at most once — re-submitting a correct guess yields nothing extra.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List

from .catalog import Song, SongCatalog
from .matching import classify_guess

Broadcast = Callable[[Dict], Awaitable[None]]
GetPlayerIds = Callable[[], List[str]]
CatalogFactory = Callable[[], "SongCatalog | None"]


@dataclass
class _Round:
    index: int
    song: Song
    deadline: float  # monotonic timestamp
    finish_timer: asyncio.Task | None = None
    found_artist: set[str] = field(default_factory=set)
    found_title: set[str] = field(default_factory=set)
    first_full: str | None = None
    # When True, _play_round returns "replay this round with a fresh song"
    # instead of broadcasting round_ended. Used when the host's player can't
    # actually play the song (region-locked, embed-disabled, etc.).
    rerun: bool = False


class GameSession:
    PHASE_IDLE = "idle"
    PHASE_PLAYING = "playing"
    PHASE_FINAL = "final"

    def __init__(
        self,
        catalog_factory: CatalogFactory,
        broadcast: Broadcast,
        get_player_ids: GetPlayerIds,
        rounds: int = 10,
        round_seconds: float = 30.0,
        hint_intervals: tuple[float, ...] = (10.0, 20.0),
        short_finish_seconds: float = 5.0,
        between_rounds_seconds: float = 2.0,
        restart_prompt_seconds: float = 10.0,
    ) -> None:
        # Resolved at start() time so it picks up whatever playlist the host
        # has loaded most recently.
        self._catalog_factory = catalog_factory
        self._broadcast = broadcast
        self._get_player_ids = get_player_ids
        self._rounds = rounds
        self._round_seconds = round_seconds
        self._hint_intervals = hint_intervals
        self._short_finish = short_finish_seconds
        self._between_rounds = between_rounds_seconds
        self._restart_prompt = restart_prompt_seconds

        self._phase = self.PHASE_IDLE
        self._round: _Round | None = None
        self._songs: list[Song] = []
        self._scores: dict[str, int] = {}
        self._completion: asyncio.Event | None = None
        self._restart_event: asyncio.Event | None = None
        self._loop_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # ---- public state ----------------------------------------------------

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def scores(self) -> dict[str, int]:
        return dict(self._scores)

    def state(self) -> dict:
        return {
            "phase": self._phase,
            "round_index": self._round.index if self._round else None,
            "total_rounds": self._rounds,
            "scores": dict(self._scores),
        }

    # ---- public commands -------------------------------------------------

    async def start(self) -> bool:
        async with self._lock:
            if self._phase != self.PHASE_IDLE:
                return False
            catalog = self._catalog_factory()
            if catalog is None:
                return False
            songs = catalog.random_sample(self._rounds)
            if not songs:
                return False
            self._songs = songs
            # Initialize scores for currently-connected players. Late joiners
            # get 0 when they answer (see _ensure_score).
            self._scores = {pid: 0 for pid in self._get_player_ids()}
            self._phase = self.PHASE_PLAYING
            self._loop_task = asyncio.create_task(self._run())
            return True

    async def submit_answer(self, player_id: str, guess: str) -> None:
        async with self._lock:
            if self._phase != self.PHASE_PLAYING or self._round is None:
                return
            round_ = self._round
            song = round_.song
            self._ensure_score(player_id)

        result = classify_guess(guess, song.artist, song.title)

        async with self._lock:
            # Re-check round hasn't changed under us
            if self._round is not round_:
                return
            new_artist = result.artist and player_id not in round_.found_artist
            new_title = result.title and player_id not in round_.found_title
            if new_artist:
                round_.found_artist.add(player_id)
                self._scores[player_id] += 1
            if new_title:
                round_.found_title.add(player_id)
                self._scores[player_id] += 1
            has_full = (
                player_id in round_.found_artist
                and player_id in round_.found_title
            )
            became_first_full = has_full and round_.first_full is None
            if became_first_full:
                round_.first_full = player_id
                self._scores[player_id] += 1  # speed bonus
                # Shrink the chrono if there's more time left than short_finish
                self._maybe_shorten_round(round_)

        kind = (
            "both"
            if result.artist and result.title
            else "artist"
            if result.artist
            else "title"
            if result.title
            else "none"
        )
        await self._broadcast(
            {
                "type": "answer_feedback",
                "player_id": player_id,
                "correct": result.any,
                "kind": kind,
                "is_first_full": became_first_full,
                "scores_total": dict(self._scores),
            }
        )

    async def skip_round(self, reason: str = "manual") -> bool:
        """Skip the current round.

        - reason="manual": end the round immediately. round_ended is
          broadcast (with the song reveal) and the next round starts.
        - reason="rights": the player's iframe can't actually play this
          song. Pick a replacement from the catalog, swap it into the
          current round, and re-play the round from scratch (same
          round_index, fresh chrono, no reveal of the unplayed song).
          Falls back to manual behaviour if no fresh song is available.
        """
        async with self._lock:
            if (
                self._phase != self.PHASE_PLAYING
                or self._round is None
                or self._completion is None
            ):
                return False
            if reason == "rights":
                replacement = self._pick_replacement_song()
                if replacement is not None:
                    self._songs[self._round.index] = replacement
                    self._round.rerun = True
            self._completion.set()
        return True

    def _pick_replacement_song(self) -> "Song | None":
        """Sample a song from the catalog that isn't already scheduled.

        Caller must hold self._lock. Returns None if no fresh candidate is
        found within a few attempts — the caller then falls back to ending
        the round normally so the session doesn't stall.
        """
        catalog = self._catalog_factory()
        if catalog is None:
            return None
        used = {
            (s.artist, s.title, s.video_id) for s in self._songs
        }
        candidates = catalog.random_sample(max(20, len(self._songs) * 2))
        for c in candidates:
            if (c.artist, c.title, c.video_id) not in used:
                return c
        return None

    async def request_restart(self) -> bool:
        """Host-triggered. Only valid during PHASE_FINAL — wakes the loop."""
        async with self._lock:
            if self._phase != self.PHASE_FINAL or self._restart_event is None:
                return False
            self._restart_event.set()
        return True

    async def cancel(self) -> None:
        """Force-stop everything (e.g., host disconnect, server shutdown)."""
        async with self._lock:
            loop_task = self._loop_task
            self._loop_task = None
        if loop_task and not loop_task.done():
            loop_task.cancel()
            try:
                await loop_task
            except (asyncio.CancelledError, Exception):
                pass
        await self._reset()

    # ---- internals -------------------------------------------------------

    def _ensure_score(self, player_id: str) -> None:
        if player_id not in self._scores:
            self._scores[player_id] = 0

    def _maybe_shorten_round(self, round_: _Round) -> None:
        remaining = round_.deadline - time.monotonic()
        if remaining <= self._short_finish:
            return
        # Replace timer with a shorter one. We cancel without awaiting:
        # the cancelled task simply returns without setting the event.
        if round_.finish_timer:
            round_.finish_timer.cancel()
        round_.deadline = time.monotonic() + self._short_finish
        round_.finish_timer = asyncio.create_task(
            self._finish_after(self._short_finish)
        )

    @staticmethod
    async def _cancel_tasks(*tasks: "asyncio.Task | None") -> None:
        pending = [t for t in tasks if t is not None and not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _finish_after(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self._completion is not None:
            self._completion.set()

    async def _send_hint_after(self, delay: float, hint_kind: str, value: str) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        await self._broadcast({"type": "hint", "kind": hint_kind, "value": value})

    async def _run(self) -> None:
        try:
            i = 0
            while i < len(self._songs):
                rerun = await self._play_round(i, self._songs[i])
                if not rerun:
                    i += 1
                # On rerun, self._songs[i] has been swapped to a fresh song
                # by skip_round("rights"); we replay the same round index.
            await self._enter_final()
        except asyncio.CancelledError:
            raise
        finally:
            # If we reached the end normally, _enter_final handled reset.
            # If we were cancelled, cancel() does the reset.
            pass

    async def _play_round(self, index: int, song: Song) -> bool:
        """Play one round. Returns True if the round should be replayed
        with a freshly-swapped-in song (the host's player couldn't play
        this one), False if it ended normally."""
        now = time.monotonic()
        round_ = _Round(
            index=index,
            song=song,
            deadline=now + self._round_seconds,
        )
        completion = asyncio.Event()

        async with self._lock:
            self._round = round_
            self._completion = completion

        round_.finish_timer = asyncio.create_task(
            self._finish_after(self._round_seconds)
        )
        hint_tasks = self._schedule_hints(song, round_.index)

        await self._broadcast(
            {
                "type": "round_started",
                "round_index": index,
                "total_rounds": self._rounds,
                "time_left_ms": int(self._round_seconds * 1000),
                "video_id": song.video_id,
            }
        )

        try:
            await completion.wait()
        finally:
            await self._cancel_tasks(round_.finish_timer, *hint_tasks)
            rerun = round_.rerun
            async with self._lock:
                self._round = None
                self._completion = None

        if rerun:
            # Don't reveal a song nobody got to hear; the next iteration of
            # _run will re-call _play_round with the replacement song.
            return True

        await self._broadcast(
            {
                "type": "round_ended",
                "round_index": index,
                "song": {
                    "artist": song.artist,
                    "title": song.title,
                    "year": song.year,
                },
                "scores_total": dict(self._scores),
            }
        )

        # Brief gap before next round so the UI can show the reveal
        if index < len(self._songs) - 1:
            await asyncio.sleep(self._between_rounds)
        return False

    def _schedule_hints(self, song: Song, round_index: int) -> list[asyncio.Task]:
        tasks: list[asyncio.Task] = []
        if len(self._hint_intervals) >= 1:
            year_value = str(song.year) if song.year is not None else "?"
            tasks.append(
                asyncio.create_task(
                    self._send_hint_after(self._hint_intervals[0], "year", year_value)
                )
            )
        if len(self._hint_intervals) >= 2:
            initials = (
                f"{_first_char(song.artist)} · {_first_char(song.title)}"
            )
            tasks.append(
                asyncio.create_task(
                    self._send_hint_after(self._hint_intervals[1], "initials", initials)
                )
            )
        return tasks

    async def _enter_final(self) -> None:
        async with self._lock:
            self._phase = self.PHASE_FINAL
            self._restart_event = asyncio.Event()
            restart_event = self._restart_event

        podium = sorted(
            (
                {"player_id": pid, "score": score}
                for pid, score in self._scores.items()
            ),
            key=lambda r: r["score"],
            reverse=True,
        )
        for rank, entry in enumerate(podium[:3], start=1):
            entry["rank"] = rank

        await self._broadcast(
            {
                "type": "session_ended",
                "podium": podium[:3],
                "scores_total": dict(self._scores),
            }
        )
        await self._broadcast(
            {
                "type": "restart_prompt",
                "deadline_ms": int(self._restart_prompt * 1000),
            }
        )

        try:
            await asyncio.wait_for(restart_event.wait(), timeout=self._restart_prompt)
            restarted = True
        except asyncio.TimeoutError:
            restarted = False

        if restarted:
            await self._reset()
            await self.start()
        else:
            await self._broadcast({"type": "session_terminated"})
            await self._reset()

    async def _reset(self) -> None:
        async with self._lock:
            self._phase = self.PHASE_IDLE
            self._round = None
            self._songs = []
            self._scores = {}
            self._completion = None
            self._restart_event = None
            # _loop_task is left as-is; the caller (cancel) or the natural end
            # of _run handles its lifecycle.


def _first_char(s: str) -> str:
    for c in s:
        if c.isalnum():
            return c.upper()
    return "?"


# Module-level singleton, wired in main.py via init().
session: "GameSession | None" = None


def init(catalog_factory: CatalogFactory, lobby) -> "GameSession":
    """Instantiate and return the module-level session singleton."""
    global session
    session = GameSession(
        catalog_factory=catalog_factory,
        broadcast=lobby.broadcast,
        get_player_ids=lambda: [p.id for p in lobby.state().players],
    )
    return session
