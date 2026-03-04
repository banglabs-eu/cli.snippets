"""Internationalization module for Snippets CLI."""

import json
import os
from pathlib import Path

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
_current_lang: str = "en"

_I18N_DIR = Path(__file__).parent / "i18n"
_LANG_FILE = Path.home() / ".snippets_cli" / "language"


def init(lang: str | None = None):
    """Load language strings. Priority: arg > persisted file > env var > 'en'."""
    global _strings, _fallback, _current_lang

    _fallback = _load("en")

    if lang is None:
        if _LANG_FILE.exists():
            lang = _LANG_FILE.read_text().strip()
        else:
            lang = os.environ.get("SNIPPETS_LANG", "en")

    _current_lang = lang
    _strings = _load(lang) if lang != "en" else _fallback


def _load(lang: str) -> dict[str, str]:
    path = _I18N_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _(key: str, **kwargs) -> str:
    """Look up a translation key with optional format interpolation."""
    template = _strings.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def _n(key_one: str, key_other: str, count: int, **kwargs) -> str:
    """Plural-aware lookup: key_one if count == 1, else key_other."""
    key = key_one if count == 1 else key_other
    return _(key, count=count, **kwargs)


def set_lang(lang: str):
    """Switch language at runtime and persist to ~/.snippets_cli/language."""
    global _strings, _current_lang
    if lang not in available_langs():
        raise ValueError(lang)
    _current_lang = lang
    _strings = _load(lang) if lang != "en" else _fallback
    _LANG_FILE.parent.mkdir(exist_ok=True)
    _LANG_FILE.write_text(lang)


def get_lang() -> str:
    return _current_lang


def available_langs() -> list[str]:
    return sorted(p.stem for p in _I18N_DIR.glob("*.json"))
