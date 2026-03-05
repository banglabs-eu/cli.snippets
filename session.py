"""Session state for Snippets CLI."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from offline import OfflineStore


class Session:
    def __init__(self):
        self.current_source_id: int | None = None
        self.current_source_name: str | None = None
        self.last_note_id: int | None = None
        self.session_note_ids: list[int] = []
        self.offline_mode: bool = False
        self.offline_store: OfflineStore | None = None

    def record_note(self, note_id: int):
        self.last_note_id = note_id
        self.session_note_ids.append(note_id)

    def reset(self):
        self.current_source_id = None
        self.current_source_name = None
        self.last_note_id = None
        self.session_note_ids.clear()
