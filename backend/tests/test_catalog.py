import random

import pytest

from app.catalog import MockCatalog, Song


def test_song_dataclass_is_immutable() -> None:
    s = Song("Queen", "Bohemian Rhapsody", 1975)
    with pytest.raises(Exception):
        s.artist = "Bowie"  # type: ignore[misc]


def test_mock_catalog_rejects_empty() -> None:
    with pytest.raises(ValueError):
        MockCatalog([])


def test_random_sample_returns_k_songs() -> None:
    catalog = MockCatalog.demo()
    sample = catalog.random_sample(5)
    assert len(sample) == 5
    assert len(set(sample)) == 5  # no duplicates


def test_random_sample_caps_at_catalog_size() -> None:
    catalog = MockCatalog([Song("A", "a"), Song("B", "b")])
    sample = catalog.random_sample(10)
    assert len(sample) == 2


def test_random_sample_zero_or_negative_returns_empty() -> None:
    catalog = MockCatalog.demo()
    assert catalog.random_sample(0) == []
    assert catalog.random_sample(-1) == []


def test_random_sample_deterministic_with_seeded_rng() -> None:
    rng_a = random.Random(42)
    rng_b = random.Random(42)
    sample_a = MockCatalog.demo(rng=rng_a).random_sample(5)
    sample_b = MockCatalog.demo(rng=rng_b).random_sample(5)
    assert sample_a == sample_b
