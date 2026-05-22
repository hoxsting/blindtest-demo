"""Tests for GameSession scoring + flow.

Uses very short timers so the suite stays under a second. The session is
cancelled in the teardown fixture so background tasks don't leak between
tests.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import pytest

from app.catalog import MockCatalog, Song
from app.session import GameSession


class Broadcaster:
    """Async-callable that records every dispatched message."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.event = asyncio.Event()

    async def __call__(self, msg: dict[str, Any]) -> None:
        self.messages.append(msg)
        self.event.set()

    def by_type(self, t: str) -> list[dict[str, Any]]:
        return [m for m in self.messages if m["type"] == t]

    def latest(self, t: str) -> dict[str, Any] | None:
        items = self.by_type(t)
        return items[-1] if items else None


async def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"timed out waiting for predicate (>{timeout}s)")


_SONGS = [
    Song("The Beatles", "Here Comes the Sun", 1969),
    Song("Queen", "Bohemian Rhapsody", 1975),
    Song("Daft Punk", "One More Time", 2000),
]


def make_session(
    broadcaster: Broadcaster,
    *,
    player_ids: list[str] | None = None,
    rounds: int = 3,
    round_seconds: float = 5.0,
    short_finish_seconds: float = 0.1,
    between_rounds_seconds: float = 0.0,
    restart_prompt_seconds: float = 0.2,
) -> GameSession:
    catalog = MockCatalog(list(_SONGS), rng=random.Random(0))
    return GameSession(
        catalog_factory=lambda: catalog,
        broadcast=broadcaster,
        get_player_ids=lambda: list(player_ids or ["alice", "bob"]),
        rounds=rounds,
        round_seconds=round_seconds,
        hint_intervals=(round_seconds * 0.33, round_seconds * 0.66),
        short_finish_seconds=short_finish_seconds,
        between_rounds_seconds=between_rounds_seconds,
        restart_prompt_seconds=restart_prompt_seconds,
    )


@pytest.fixture
async def broadcaster() -> Broadcaster:
    return Broadcaster()


# ---- start / state -----------------------------------------------------


async def test_start_initializes_scores_for_known_players(broadcaster):
    session = make_session(broadcaster, player_ids=["alice", "bob"])
    try:
        assert await session.start()
        await wait_for(lambda: bool(broadcaster.by_type("round_started")))
        assert session.scores == {"alice": 0, "bob": 0}
        assert session.phase == GameSession.PHASE_PLAYING
    finally:
        await session.cancel()


async def test_start_rejects_when_already_playing(broadcaster):
    session = make_session(broadcaster)
    try:
        assert await session.start()
        assert not await session.start()
    finally:
        await session.cancel()


async def test_submit_ignored_when_idle(broadcaster):
    session = make_session(broadcaster)
    # No start
    await session.submit_answer("alice", "Beatles")
    assert broadcaster.by_type("answer_feedback") == []


# ---- scoring -----------------------------------------------------------


async def test_artist_only_scores_one_point(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        await session.submit_answer("alice", song.artist)
        fb = broadcaster.latest("answer_feedback")
        assert fb["correct"] is True
        assert fb["kind"] == "artist"
        assert fb["is_first_full"] is False
        assert session.scores["alice"] == 1
        assert session.scores["bob"] == 0
    finally:
        await session.cancel()


async def test_title_only_scores_one_point(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        await session.submit_answer("alice", song.title)
        assert session.scores["alice"] == 1
    finally:
        await session.cancel()


async def test_full_match_grants_two_plus_bonus(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        await session.submit_answer("alice", song.artist)
        await session.submit_answer("alice", song.title)
        # 1 (artist) + 1 (title) + 1 (first-full bonus) = 3
        assert session.scores["alice"] == 3
        fb = broadcaster.latest("answer_feedback")
        assert fb["is_first_full"] is True
    finally:
        await session.cancel()


async def test_second_player_full_match_no_bonus(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        await session.submit_answer("alice", song.artist)
        await session.submit_answer("alice", song.title)
        # Bob gets full but loses bonus
        await session.submit_answer("bob", song.artist)
        await session.submit_answer("bob", song.title)
        assert session.scores["alice"] == 3
        assert session.scores["bob"] == 2
    finally:
        await session.cancel()


async def test_resubmitting_correct_guess_no_double_credit(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        await session.submit_answer("alice", song.artist)
        await session.submit_answer("alice", song.artist)
        await session.submit_answer("alice", song.artist)
        assert session.scores["alice"] == 1
    finally:
        await session.cancel()


async def test_wrong_guess_no_score_change(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        await session.submit_answer("alice", "totally wrong garbage")
        fb = broadcaster.latest("answer_feedback")
        assert fb["correct"] is False
        assert fb["kind"] == "none"
        assert session.scores["alice"] == 0
    finally:
        await session.cancel()


async def test_late_joiner_gets_score_initialized(broadcaster):
    session = make_session(broadcaster, player_ids=["alice"], round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        # "charlie" wasn't in the lobby at start
        await session.submit_answer("charlie", "anything")
        assert "charlie" in session.scores
        assert session.scores["charlie"] == 0
    finally:
        await session.cancel()


# ---- round shortening on full match -----------------------------------


async def test_full_match_shortens_round(broadcaster):
    # Round of 10s, short_finish 0.1s — round should end ~0.1s after full match
    session = make_session(
        broadcaster, round_seconds=10.0, short_finish_seconds=0.1
    )
    try:
        await session.start()
        await wait_for(lambda: session._round is not None)
        song = session._round.song
        start = time.monotonic()
        await session.submit_answer("alice", song.artist)
        await session.submit_answer("alice", song.title)
        # Wait for round_ended (after the shortened deadline)
        await wait_for(lambda: bool(broadcaster.by_type("round_ended")))
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"round did not shorten (took {elapsed:.2f}s)"
    finally:
        await session.cancel()


# ---- session lifecycle -------------------------------------------------


async def test_session_runs_all_rounds_then_enters_final(broadcaster):
    # Use very short rounds; no answers → all rounds time out
    session = make_session(
        broadcaster,
        rounds=2,
        round_seconds=0.05,
        between_rounds_seconds=0.0,
        restart_prompt_seconds=0.5,
    )
    try:
        await session.start()
        await wait_for(
            lambda: bool(broadcaster.by_type("session_ended")), timeout=3.0
        )
        ended = broadcaster.latest("session_ended")
        assert ended is not None
        assert "podium" in ended
        # All rounds completed, scores all zero (no answers)
        assert all(v == 0 for v in ended["scores_total"].values())
        # Phase should be FINAL while waiting for restart
        assert session.phase == GameSession.PHASE_FINAL
    finally:
        await session.cancel()


async def test_session_terminates_if_no_restart(broadcaster):
    session = make_session(
        broadcaster,
        rounds=1,
        round_seconds=0.05,
        between_rounds_seconds=0.0,
        restart_prompt_seconds=0.1,
    )
    try:
        await session.start()
        await wait_for(
            lambda: bool(broadcaster.by_type("session_terminated")), timeout=3.0
        )
        assert session.phase == GameSession.PHASE_IDLE
    finally:
        await session.cancel()


async def test_request_restart_loops_back_to_playing(broadcaster):
    session = make_session(
        broadcaster,
        rounds=1,
        round_seconds=0.05,
        between_rounds_seconds=0.0,
        restart_prompt_seconds=1.0,
    )
    try:
        await session.start()
        await wait_for(
            lambda: session.phase == GameSession.PHASE_FINAL, timeout=2.0
        )
        # Capture how many session_ended we've seen so far
        seen = len(broadcaster.by_type("round_started"))
        assert await session.request_restart()
        # A new round_started should appear
        await wait_for(
            lambda: len(broadcaster.by_type("round_started")) > seen, timeout=2.0
        )
    finally:
        await session.cancel()


async def test_request_restart_noop_when_not_in_final(broadcaster):
    session = make_session(broadcaster, round_seconds=10.0)
    try:
        await session.start()
        await wait_for(lambda: session.phase == GameSession.PHASE_PLAYING)
        assert not await session.request_restart()
    finally:
        await session.cancel()
