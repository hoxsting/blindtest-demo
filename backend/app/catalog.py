"""Song catalog abstraction.

The game session depends only on `SongCatalog`. The Spotify implementation
will be plugged in later (handled by another dev). `MockCatalog` lets us
develop and test the session without that dependency.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Song:
    artist: str
    title: str
    year: int | None = None


class SongCatalog(Protocol):
    def random_sample(self, k: int) -> list[Song]: ...


class MockCatalog:
    """In-memory catalog used for local development and tests.

    Sample is uniform and without replacement. If `k` exceeds the catalog
    size, returns the whole catalog shuffled.
    """

    def __init__(self, songs: list[Song], rng: random.Random | None = None) -> None:
        if not songs:
            raise ValueError("MockCatalog requires at least one song")
        self._songs = list(songs)
        self._rng = rng or random.Random()

    def random_sample(self, k: int) -> list[Song]:
        if k <= 0:
            return []
        n = min(k, len(self._songs))
        return self._rng.sample(self._songs, n)

    @classmethod
    def demo(cls, rng: random.Random | None = None) -> "MockCatalog":
        """A small built-in demo catalog so the game is playable out of the box."""
        return cls(_DEMO_SONGS, rng=rng)


_DEMO_SONGS: list[Song] = [
    Song("The Beatles", "Here Comes the Sun", 1969),
    Song("Queen", "Bohemian Rhapsody", 1975),
    Song("Nirvana", "Smells Like Teen Spirit", 1991),
    Song("Daft Punk", "Around the World", 1997),
    Song("Coldplay", "Yellow", 2000),
    Song("Beyoncé", "Crazy in Love", 2003),
    Song("Adele", "Rolling in the Deep", 2010),
    Song("Pharrell Williams", "Happy", 2013),
    Song("Stromae", "Papaoutai", 2013),
    Song("Edith Piaf", "La Vie en Rose", 1947),
    Song("Joe Dassin", "Les Champs-Élysées", 1969),
    Song("Michael Jackson", "Billie Jean", 1982),
    Song("ABBA", "Dancing Queen", 1976),
    Song("Mylène Farmer", "Désenchantée", 1991),
    Song("Francis Cabrel", "Petite Marie", 1977),
    Song("U2", "One", 1991),
    Song("Bruno Mars", "24K Magic", 2016),
    Song("Billie Eilish", "Bad Guy", 2019),
    Song("Dua Lipa", "Houdini", 2023),
    Song("Indochine", "J'ai demandé à la lune", 2002),
]
