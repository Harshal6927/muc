# Copyright (c) 2025. All rights reserved.
"""Tests for the search module."""

import pytest

from src.search import SearchResult, fuzzy_match, highlight_match, search_sounds


class TestFuzzyMatch:
    """Tests for fuzzy_match function."""

    def test_exact_match(self) -> None:
        """Test exact match returns score of 1.0."""
        assert fuzzy_match("airhorn", "airhorn") == 1.0
        assert fuzzy_match("Airhorn", "airhorn") == 1.0  # Case insensitive

    def test_prefix_match(self) -> None:
        """Test prefix match returns high score."""
        score = fuzzy_match("air", "airhorn")
        assert 0.9 < score < 1.0

    def test_contains_match(self) -> None:
        """Test contains match returns medium-high score."""
        score = fuzzy_match("horn", "airhorn")
        assert 0.7 < score < 0.9

    def test_fuzzy_match(self) -> None:
        """Test fuzzy match for typos."""
        score = fuzzy_match("airhon", "airhorn")  # Typo
        assert score > 0.3

    def test_no_match(self) -> None:
        """Test no match returns low score."""
        score = fuzzy_match("xyz", "airhorn")
        assert score < 0.3


class TestSearchSounds:
    """Tests for search_sounds function."""

    @pytest.fixture
    def sample_sounds(self) -> dict:
        """Fixture providing sample sound dictionary.

        Returns:
            Dictionary of sound names to paths.

        """
        return {
            "airhorn": "/path/to/airhorn.mp3",
            "rickroll": "/path/to/rickroll.mp3",
            "explosion": "/path/to/explosion.mp3",
            "applause": "/path/to/applause.mp3",
            "dramatic": "/path/to/dramatic.mp3",
        }

    @pytest.fixture
    def sample_tags(self) -> dict:
        """Fixture providing sample tags dictionary.

        Returns:
            Dictionary of sound names to tag lists.

        """
        return {
            "airhorn": ["loud", "meme"],
            "rickroll": ["meme", "music"],
            "explosion": ["loud", "effect"],
            "applause": ["effect"],
            "dramatic": ["music", "effect"],
        }

    def test_empty_query(self, sample_sounds: dict) -> None:
        """Test empty query returns no results."""
        results = search_sounds("", sample_sounds)
        assert results == []

    def test_exact_match(self, sample_sounds: dict) -> None:
        """Test exact match is found first."""
        results = search_sounds("airhorn", sample_sounds)
        assert len(results) > 0
        assert results[0].name == "airhorn"
        assert results[0].match_type == "exact"
        assert results[0].score == 1.0

    def test_prefix_match(self, sample_sounds: dict) -> None:
        """Test prefix match is found."""
        results = search_sounds("air", sample_sounds)
        assert len(results) > 0
        assert results[0].name == "airhorn"
        assert results[0].match_type == "prefix"

    def test_contains_match(self, sample_sounds: dict) -> None:
        """Test contains match is found."""
        results = search_sounds("horn", sample_sounds)
        assert len(results) > 0
        assert results[0].name == "airhorn"
        assert results[0].match_type == "contains"

    def test_fuzzy_match(self, sample_sounds: dict) -> None:
        """Test fuzzy match for typos."""
        results = search_sounds("rcikroll", sample_sounds)  # Transposed letters
        assert len(results) > 0
        assert results[0].name == "rickroll"
        assert results[0].match_type == "fuzzy"

    def test_tag_search(self, sample_sounds: dict, sample_tags: dict) -> None:
        """Test search by tag."""
        results = search_sounds("loud", sample_sounds, tags=sample_tags)
        assert len(results) >= 2
        # Should find airhorn and explosion (both have "loud" tag)
        result_names = [r.name for r in results]
        assert "airhorn" in result_names or "explosion" in result_names

    def test_limit_results(self, sample_sounds: dict) -> None:
        """Test limiting number of results."""
        results = search_sounds("a", sample_sounds, limit=2)
        assert len(results) <= 2

    def test_min_score_filter(self, sample_sounds: dict) -> None:
        """Test minimum score filtering."""
        # Search with high min_score
        results = search_sounds("xyz", sample_sounds, min_score=0.5)
        assert len(results) == 0

    def test_results_sorted_by_score(self, sample_sounds: dict) -> None:
        """Test results are sorted by score descending."""
        results = search_sounds("a", sample_sounds)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score


class TestHighlightMatch:
    """Tests for highlight_match function."""

    def test_highlight_found(self) -> None:
        """Test highlighting when match is found."""
        result = highlight_match("airhorn", "air")
        assert result == "[bold cyan]air[/bold cyan]horn"

    def test_highlight_not_found(self) -> None:
        """Test when no match is found."""
        result = highlight_match("airhorn", "xyz")
        assert result == "airhorn"

    def test_highlight_case_insensitive(self) -> None:
        """Test case-insensitive highlighting."""
        result = highlight_match("AirHorn", "air")
        assert result == "[bold cyan]Air[/bold cyan]Horn"


class TestSearchResult:
    """Tests for SearchResult named tuple."""

    def test_create_result(self) -> None:
        """Test creating a SearchResult."""
        result = SearchResult(name="test", score=0.8, match_type="prefix")
        assert result.name == "test"
        assert result.score == 0.8
        assert result.match_type == "prefix"

    def test_result_is_named_tuple(self) -> None:
        """Test SearchResult is a proper named tuple."""
        result = SearchResult("test", 0.8, "exact")
        name, score, match_type = result
        assert name == "test"
        assert score == 0.8
        assert match_type == "exact"
