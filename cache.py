# cache.py
import json
import os
from config import CACHE_FILE


def _normalize(filepath: str) -> str:
    """
    Normalize file path so it always matches in cache regardless of:
    - forward vs back slashes
    - trailing slashes
    - case differences on Windows
    - extra spaces
    """
    return os.path.normcase(os.path.normpath(filepath.strip()))


def _load() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save(data: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_cached_row_count(filepath: str) -> int:
    """Return the row count we saw last time for this file. 0 if never seen."""
    key = _normalize(filepath)
    raw = _load()
    # Also check normalized versions of all existing keys
    for k, v in raw.items():
        if _normalize(k) == key:
            return v.get("row_count", 0)
    return 0


def update_cache(filepath: str, row_count: int):
    """Save the new row count for this file."""
    key  = _normalize(filepath)
    data = _load()
    # Remove any existing entry with the same normalized path
    # to avoid duplicate keys with different slash styles
    keys_to_remove = [k for k in data if _normalize(k) == key]
    for k in keys_to_remove:
        del data[k]
    # Store with the normalized key
    data[key] = {"row_count": row_count}
    _save(data)