"""
tests/test_tools.py

Tests for the three FitFindr tools. All tests here avoid calling the LLM
so they run without a GROQ_API_KEY and complete in < 1 second.
"""

import pytest
from tools import search_listings, create_fit_card


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_no_price_filter_returns_more():
    without_filter = search_listings("jacket", size=None, max_price=None)
    with_filter = search_listings("jacket", size=None, max_price=10)
    assert len(without_filter) >= len(with_filter)


def test_search_size_filter_case_insensitive():
    results = search_listings("tee", size="m", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_returns_list_not_exception_on_no_match():
    results = search_listings("xyzzy nonexistent item abc", size=None, max_price=None)
    assert isinstance(results, list)
    assert results == []


def test_search_sorted_by_relevance():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) > 1
    # All returned items must have at least one keyword match (score > 0)
    for item in results:
        text = (
            item["title"].lower()
            + " "
            + item["description"].lower()
            + " "
            + " ".join(item["style_tags"]).lower()
        )
        assert "vintage" in text


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    dummy_item = {
        "title": "Test Tee",
        "price": 20.0,
        "platform": "depop",
        "style_tags": ["vintage"],
        "colors": ["black"],
        "category": "tops",
        "description": "A test tee.",
        "size": "M",
        "condition": "good",
    }
    result = create_fit_card("", dummy_item)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Error" in result


def test_create_fit_card_whitespace_outfit_returns_error_string():
    dummy_item = {
        "title": "Test Tee",
        "price": 20.0,
        "platform": "depop",
        "style_tags": ["vintage"],
        "colors": ["black"],
        "category": "tops",
        "description": "A test tee.",
        "size": "M",
        "condition": "good",
    }
    result = create_fit_card("   ", dummy_item)
    assert isinstance(result, str)
    assert "Error" in result
