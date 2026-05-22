import pytest

from app.matching import (
    GuessResult,
    classify_guess,
    levenshtein,
    matches,
    normalize,
    tolerance,
)


class TestNormalize:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Hello", "hello"),
            ("HELLO", "hello"),
            ("Édith Piaf", "edith piaf"),
            ("Mañana", "manana"),
            ("Beyoncé", "beyonce"),
            ("Don't stop", "don t stop"),
            ("Hello, World!", "hello world"),
            ("  multiple   spaces  ", "multiple spaces"),
            ("", ""),
            ("The Beatles", "beatles"),
            ("the beatles", "beatles"),
            ("Les Innocents", "innocents"),
            ("La Vie en Rose", "vie en rose"),
            ("L'Amour", "amour"),
            ("L'amour toujours", "amour toujours"),
            ("Rock & Roll", "rock and roll"),
            ("AC/DC", "ac dc"),
        ],
    )
    def test_basic_normalization(self, raw: str, expected: str) -> None:
        assert normalize(raw) == expected

    def test_only_strips_leading_article(self) -> None:
        # "Le" in the middle stays
        assert normalize("Tu es le meilleur") == "tu es le meilleur"


class TestTolerance:
    @pytest.mark.parametrize(
        "expected, expected_tolerance",
        [
            ("U2", 0),  # 2 chars
            ("ABC", 0),  # 3 chars
            ("Stop", 1),  # 4 chars
            ("Banana", 1),  # 6 chars
            ("Madonna", 2),  # 7 chars
            ("Beatles", 2),  # 7 chars
            ("Aerosmith", 2),  # 9 chars
            ("Radiohead", 2),  # 9 chars
            ("Coldplay X", 2),  # 10 chars
            ("Imagine Dragons", 3),  # 15 chars
            ("Red Hot Chili Peppers", 3),  # 21 chars
        ],
    )
    def test_tolerance_by_length(self, expected: str, expected_tolerance: int) -> None:
        assert tolerance(expected) == expected_tolerance

    def test_tolerance_accounts_for_accents_stripped(self) -> None:
        # "Beyoncé" → "beyonce" (7 chars) → 2
        assert tolerance("Beyoncé") == 2

    def test_tolerance_accounts_for_leading_article(self) -> None:
        # "The Beatles" → "beatles" (7 chars) → 2, not 11→3
        assert tolerance("The Beatles") == 2


class TestLevenshtein:
    @pytest.mark.parametrize(
        "a, b, dist",
        [
            ("hello", "hello", 0),
            ("hello", "hallo", 1),
            ("hello", "helo", 1),
            ("hello", "helloo", 1),
            ("hello", "world", 4),
            ("", "abc", 3),
            ("abc", "", 3),
            ("kitten", "sitting", 3),
        ],
    )
    def test_distance(self, a: str, b: str, dist: int) -> None:
        assert levenshtein(a, b) == dist


class TestMatches:
    def test_exact_match(self) -> None:
        assert matches("Beatles", "The Beatles")

    def test_accents_ignored(self) -> None:
        assert matches("beyonce", "Beyoncé")
        assert matches("Edith Piaf", "édith piaf")

    def test_punctuation_ignored(self) -> None:
        assert matches("dont stop", "Don't stop")

    def test_within_tolerance(self) -> None:
        # "Madonna" → 7 chars → tolerance 2
        assert matches("Madona", "Madonna")  # 1 deletion
        assert matches("Madomna", "Madonna")  # 1 substitution

    def test_beyond_tolerance(self) -> None:
        # "U2" → 2 chars → tolerance 0, no edit allowed
        assert not matches("U3", "U2")
        # "Stop" → 4 chars → tolerance 1; "Spot" vs "Stop" is distance 2 → reject
        assert not matches("Spot", "Stop")

    def test_empty_guess_does_not_match(self) -> None:
        assert not matches("", "Beatles")
        assert not matches("  ", "Beatles")

    def test_article_stripped_on_both_sides(self) -> None:
        assert matches("The Beatles", "Beatles")
        assert matches("Beatles", "The Beatles")
        assert matches("L'amour", "amour")


class TestClassifyGuess:
    SONG_ARTIST = "The Beatles"
    SONG_TITLE = "Here Comes the Sun"

    def test_guess_matches_artist_only(self) -> None:
        r = classify_guess("Beatles", self.SONG_ARTIST, self.SONG_TITLE)
        assert r == GuessResult(artist=True, title=False)
        assert r.any
        assert not r.both

    def test_guess_matches_title_only(self) -> None:
        r = classify_guess("Here Comes the Sun", self.SONG_ARTIST, self.SONG_TITLE)
        assert r == GuessResult(artist=False, title=True)
        assert r.any
        assert not r.both

    def test_guess_matches_nothing(self) -> None:
        r = classify_guess("Bohemian Rhapsody", self.SONG_ARTIST, self.SONG_TITLE)
        assert not r.any

    def test_guess_could_match_both_if_overlap(self) -> None:
        # Edge case: artist and title share a string. Possible if the artist's
        # name appears in the title.
        r = classify_guess("X", "X", "X")
        assert r.both
