"""
Persist and retrieve user style profiles across sessions.

Profiles are stored as JSON files in the profiles/ directory at the repo root,
keyed by the profile name the user enters in the UI.
"""

import json
import os

_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "..", "profiles")


def save_profile(
    name: str,
    size: str | None,
    max_price: float | None,
    style_keywords: list[str],
) -> None:
    """Write (or overwrite) the profile JSON for the given name."""
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    path = os.path.join(_PROFILES_DIR, f"{name}.json")
    data = {
        "name": name,
        "size": size,
        "max_price": max_price,
        "style_keywords": style_keywords,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_profile(name: str) -> dict | None:
    """
    Load the profile for the given name.
    Returns None if no profile file exists.
    """
    path = os.path.join(_PROFILES_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
