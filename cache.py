"""Local cache of backend data for offline autocomplete."""

import json
from pathlib import Path

import client

CACHE_FILE = Path.home() / ".snippets_cli" / "cache.json"

_data: dict = {"sources": [], "tags": [], "authors": []}


def load():
    """Load cache from disk into memory."""
    global _data
    if CACHE_FILE.exists():
        try:
            _data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _data = {"sources": [], "tags": [], "authors": []}


def refresh():
    """Fetch all sources, tags, and authors from the backend and save locally."""
    global _data
    _data = {
        "sources": client.get_all_sources(),
        "tags": client.get_all_tags(),
        "authors": client.get_all_authors(),
    }
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(_data, ensure_ascii=False), encoding="utf-8")


# ── search helpers (mirror client API, work on local data) ──

def search_sources(prefix: str) -> list[dict]:
    prefix = prefix.lower()
    return [s for s in _data["sources"] if prefix in s["name"].lower()]


def get_recent_sources(limit: int = 10) -> list[dict]:
    return _data["sources"][-limit:]


def search_tags(prefix: str) -> list[dict]:
    prefix = prefix.lower()
    return [t for t in _data["tags"] if t["name"].lower().startswith(prefix)]


def get_recent_tags(limit: int = 10) -> list[dict]:
    return _data["tags"][-limit:]


def search_authors(prefix: str) -> list[dict]:
    prefix = prefix.lower()
    return [a for a in _data["authors"]
            if prefix in a["last_name"].lower() or prefix in a["first_name"].lower()]


def get_recent_authors(limit: int = 10) -> list[dict]:
    return _data["authors"][-limit:]
