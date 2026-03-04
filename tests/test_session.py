"""Tests for session.py — Session state management."""

from session import Session


class TestInit:
    def test_defaults(self):
        s = Session()
        assert s.current_source_id is None
        assert s.last_note_id is None
        assert s.session_note_ids == []


class TestRecordNote:
    def test_updates_last_note_id(self):
        s = Session()
        s.record_note(42)
        assert s.last_note_id == 42

    def test_appends_to_session_note_ids(self):
        s = Session()
        s.record_note(1)
        s.record_note(2)
        s.record_note(3)
        assert s.session_note_ids == [1, 2, 3]

    def test_last_note_id_is_most_recent(self):
        s = Session()
        s.record_note(10)
        s.record_note(20)
        assert s.last_note_id == 20


class TestReset:
    def test_clears_everything(self):
        s = Session()
        s.current_source_id = 5
        s.record_note(10)
        s.record_note(20)
        s.reset()
        assert s.current_source_id is None
        assert s.last_note_id is None
        assert s.session_note_ids == []

    def test_idempotent(self):
        s = Session()
        s.reset()
        s.reset()
        assert s.current_source_id is None
        assert s.last_note_id is None
        assert s.session_note_ids == []

    def test_list_usable_after_reset(self):
        s = Session()
        s.record_note(1)
        s.reset()
        s.record_note(99)
        assert s.session_note_ids == [99]
        assert s.last_note_id == 99
