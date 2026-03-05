"""Offline note storage — saves notes to a local Markdown file when the backend is unreachable."""

import re
from datetime import datetime
from pathlib import Path

import client

OFFLINE_FILE = Path.home() / ".snippets_cli" / "offline_notes.md"


class OfflineStore:
    def __init__(self):
        self.notes: list[dict] = []
        self._load()

    def add_note(self, body: str, source_name: str | None = None,
                 locator_type: str | None = None,
                 locator_value: str | None = None) -> int:
        self.notes.append({
            "body": body,
            "source_name": source_name,
            "tags": [],
            "locator_type": locator_type,
            "locator_value": locator_value,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._save()
        return len(self.notes)

    def add_tags_to_last(self, tag_names: list[str]) -> bool:
        if not self.notes:
            return False
        for name in tag_names:
            if name not in self.notes[-1]["tags"]:
                self.notes[-1]["tags"].append(name)
        self._save()
        return True

    def add_tags_to_note(self, index: int, tag_names: list[str]) -> bool:
        if index < 0 or index >= len(self.notes):
            return False
        for name in tag_names:
            if name not in self.notes[index]["tags"]:
                self.notes[index]["tags"].append(name)
        self._save()
        return True

    def remove_tags_from_note(self, index: int, tag_names: list[str]) -> bool:
        if index < 0 or index >= len(self.notes):
            return False
        lower_names = [n.lower() for n in tag_names]
        self.notes[index]["tags"] = [
            t for t in self.notes[index]["tags"] if t.lower() not in lower_names
        ]
        self._save()
        return True

    def count(self) -> int:
        return len(self.notes)

    def clear(self):
        self.notes.clear()
        if OFFLINE_FILE.exists():
            OFFLINE_FILE.unlink()

    # ── persistence ──

    def _save(self):
        OFFLINE_FILE.parent.mkdir(exist_ok=True)
        lines = ["# Offline Notes", ""]
        for note in self.notes:
            meta = _build_meta(note)
            lines.append(meta)
            lines.append("")
            lines.append(note["body"])
            lines.append("")
            lines.append("---")
            lines.append("")
        OFFLINE_FILE.write_text("\n".join(lines), encoding="utf-8")

    def _load(self):
        if not OFFLINE_FILE.exists():
            return
        text = OFFLINE_FILE.read_text(encoding="utf-8")
        self.notes = _parse_offline_md(text)


def _build_meta(note: dict) -> str:
    parts = []
    if note.get("source_name"):
        parts.append(f"Source: {note['source_name']}")
    if note.get("locator_type") and note.get("locator_value"):
        parts.append(f"{note['locator_type']}: {note['locator_value']}")
    if note.get("tags"):
        parts.append(f"Tags: {', '.join(note['tags'])}")
    parts.append(note["created_at"])
    return " | ".join(parts)


def _parse_offline_md(text: str) -> list[dict]:
    notes = []
    blocks = re.split(r'\n---\n', text)
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("# "):
            continue
        lines = block.split("\n")
        meta_line = lines[0].strip()
        body_lines = [l for l in lines[1:] if l is not None]
        body = "\n".join(body_lines).strip()
        note = _parse_meta(meta_line)
        note["body"] = body
        notes.append(note)
    return notes


def _parse_meta(meta: str) -> dict:
    note = {
        "source_name": None,
        "locator_type": None,
        "locator_value": None,
        "tags": [],
        "created_at": "",
        "body": "",
    }
    parts = [p.strip() for p in meta.split("|")]
    for part in parts:
        if part.startswith("Source:"):
            note["source_name"] = part[len("Source:"):].strip()
        elif part.startswith("page:"):
            note["locator_type"] = "page"
            note["locator_value"] = part[len("page:"):].strip()
        elif part.startswith("time:"):
            note["locator_type"] = "time"
            note["locator_value"] = part[len("time:"):].strip()
        elif part.startswith("Tags:"):
            raw = part[len("Tags:"):].strip()
            note["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
        else:
            # Assume it's the timestamp (last field)
            note["created_at"] = part
    return note


# ── sync ──

def has_offline_notes() -> bool:
    return OFFLINE_FILE.exists() and OFFLINE_FILE.stat().st_size > 0


def sync_offline_notes() -> int:
    """Upload offline notes to the backend. Returns number synced."""
    store = OfflineStore()
    if not store.notes:
        return 0

    synced = 0
    source_cache: dict[str, int] = {}

    for note in store.notes:
        source_id = None
        if note["source_name"]:
            if note["source_name"] in source_cache:
                source_id = source_cache[note["source_name"]]
            else:
                source_id = _resolve_or_create_source(note["source_name"])
                source_cache[note["source_name"]] = source_id

        note_id = client.create_note(
            note["body"],
            source_id=source_id,
            locator_type=note.get("locator_type"),
            locator_value=note.get("locator_value"),
        )

        for tag_name in note.get("tags", []):
            tag_id = client.get_or_create_tag(tag_name)
            client.add_tag_to_note(note_id, tag_id)

        synced += 1

    store.clear()
    return synced


def _resolve_or_create_source(name: str) -> int:
    matches = client.search_sources(name)
    exact = [m for m in matches if m["name"].lower() == name.lower()]
    if exact:
        return exact[0]["id"]
    return client.create_source(name)
