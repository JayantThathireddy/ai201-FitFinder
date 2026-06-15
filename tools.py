"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()

    # Filter by price and size
    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    # Score each listing by keyword overlap with description
    keywords = [kw.lower() for kw in description.split() if len(kw) > 2]

    def score(listing):
        points = 0
        title_words = listing["title"].lower()
        desc_words = listing["description"].lower()
        style_tags = " ".join(listing["style_tags"]).lower()
        category = listing["category"].lower()
        for kw in keywords:
            if kw in title_words:
                points += 3
            if kw in style_tags:
                points += 2
            if kw in category:
                points += 2
            if kw in desc_words:
                points += 1
        return points

    scored = [(score(listing), listing) for listing in filtered]
    scored = [(s, listing) for s, listing in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item.
    """
    client = _get_groq_client()

    item_summary = (
        f"Title: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Condition: {new_item['condition']}"
    )

    if not wardrobe.get("items"):
        prompt = (
            f"The user is considering buying this thrifted item:\n\n{item_summary}\n\n"
            "They haven't shared their wardrobe yet. Suggest 1–2 general styling ideas "
            "for this piece: what kinds of items pair well with it, what overall vibe it "
            "suits, and one specific way to wear it. Be concrete and helpful."
        )
    else:
        wardrobe_lines = []
        for item in wardrobe["items"]:
            notes = f" ({item['notes']})" if item.get("notes") else ""
            wardrobe_lines.append(
                f"- {item['name']}{notes} — colors: {', '.join(item['colors'])}"
            )
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            f"The user is considering buying this thrifted item:\n\n{item_summary}\n\n"
            f"Their existing wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific "
            "named pieces from their wardrobe. Name the exact wardrobe pieces in each "
            "combination and briefly describe the overall vibe."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a personal stylist helping thrift shoppers build great outfits. Be specific, concise, and authentic.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error string.
    """
    if not outfit or not outfit.strip():
        return "Error: No outfit suggestion available — cannot generate a fit card."

    client = _get_groq_client()

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']} on {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person posting an OOTD, not a product listing\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the outfit vibe in specific, evocative terms\n"
        "- Keep it casual, short, and shareable\n"
        "- No hashtags"
    )

    response = _get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You write casual, authentic Instagram and TikTok outfit captions that sound like real people, not brands.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1.0,
    )
    return response.choices[0].message.content.strip()
