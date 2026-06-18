# cache.py  — remembers row counts per file so we skip reprocessing unchanged files
import json
import os
from config import CACHE_FILE


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
    return _load().get(filepath, {}).get("row_count", 0)


def update_cache(filepath: str, row_count: int):
    """Save the new row count for this file."""
    data = _load()
    data[filepath] = {"row_count": row_count}
    _save(data)