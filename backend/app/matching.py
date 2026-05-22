"""Answer matching for blind test guesses.

Tolerance is based on the *expected* answer length (artist or title), not the
guess length — so a misspelled short answer stays strict, while a long one is
forgiving. Specs: ≤3→0, 4-6→1, 7-10→2, >10→3 edits allowed (Levenshtein).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_LEADING_ARTICLES = ("the", "le", "la", "les", "l", "un", "une")


def normalize(text: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace, drop leading article."""
    if not text:
        return ""
    # NFD then drop combining marks (accents)
    nfd = unicodedata.normalize("NFD", text)
    no_accents = "".join(c for c in nfd if not unicodedata.combining(c))
    # Replace "&" with "and" before stripping punctuation
    no_accents = no_accents.replace("&", " and ")
    lowered = no_accents.casefold()
    # Strip "L'" before punctuation removal so "L'amour" → "amour"
    lowered = re.sub(r"\bl'\s*", "", lowered)
    no_punct = _PUNCT_RE.sub(" ", lowered)
    collapsed = _WS_RE.sub(" ", no_punct).strip()
    # Drop a single leading article token
    parts = collapsed.split(" ", 1)
    if len(parts) == 2 and parts[0] in _LEADING_ARTICLES:
        collapsed = parts[1]
    return collapsed


def tolerance(expected: str) -> int:
    """Max Levenshtein distance allowed for a match, by normalized length."""
    n = len(normalize(expected))
    if n <= 3:
        return 0
    if n <= 6:
        return 1
    if n <= 10:
        return 2
    return 3


def levenshtein(a: str, b: str) -> int:
    """Classic O(m*n) Levenshtein distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def matches(guess: str, expected: str) -> bool:
    """True if normalized guess is within tolerance of normalized expected."""
    g = normalize(guess)
    e = normalize(expected)
    if not g or not e:
        return False
    return levenshtein(g, e) <= tolerance(expected)


@dataclass(frozen=True)
class GuessResult:
    artist: bool
    title: bool

    @property
    def any(self) -> bool:
        return self.artist or self.title

    @property
    def both(self) -> bool:
        return self.artist and self.title


def classify_guess(guess: str, artist: str, title: str) -> GuessResult:
    """Identify whether the single-field guess matches the artist, title, or both."""
    return GuessResult(
        artist=matches(guess, artist),
        title=matches(guess, title),
    )
