"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex. No LLM call — deterministic and fast.

    Examples:
        "vintage graphic tee under $30"      → description="vintage graphic tee", max_price=30.0
        "90s track jacket in size M"          → description="90s track jacket in", size="M"
        "black combat boots size 8"           → description="black combat boots", size="8"
        "designer ballgown size XXS under $5" → description="designer ballgown", size="XXS", max_price=5.0
    """
    size_match = re.search(r"\bsize\s+([A-Za-z0-9/]+)", query, re.IGNORECASE)
    price_match = re.search(r"under\s*\$?(\d+\.?\d*)", query, re.IGNORECASE)

    size = size_match.group(1) if size_match else None
    max_price = float(price_match.group(1)) if price_match else None

    description = re.sub(r"\bsize\s+[A-Za-z0-9/]+", "", query, flags=re.IGNORECASE)
    description = re.sub(r"\bunder\s*\$?\d+\.?\d*", "", description, flags=re.IGNORECASE)
    description = re.sub(r"\s{2,}", " ", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict. Check session["error"] first — if not None, the
        interaction ended early and outfit_suggestion/fit_card will be None.
    """
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query
    session["parsed"] = _parse_query(query)

    # Step 3: Search listings
    session["search_results"] = search_listings(
        description=session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )

    if not session["search_results"]:
        parts = [f"'{session['parsed']['description']}'"]
        if session["parsed"]["size"]:
            parts.append(f"in size {session['parsed']['size']}")
        if session["parsed"]["max_price"] is not None:
            parts.append(f"under ${session['parsed']['max_price']:.0f}")
        session["error"] = (
            f"No listings found for {' '.join(parts)}. "
            "Try removing the size filter, raising the price limit, or using different keywords."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = session["search_results"][0]

    # Step 5: Suggest outfit
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 6: Create fit card
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
