"""Session state for Snippets CLI."""


class Session:
    def __init__(self):
        self.current_source_id: int | None = None
        self.last_note_id: int | None = None
        self.session_note_ids: list[int] = []

    def record_note(self, note_id: int):
        self.last_note_id = note_id
        self.session_note_ids.append(note_id)
