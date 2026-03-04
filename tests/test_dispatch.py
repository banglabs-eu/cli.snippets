"""Tests for commands.py — dispatch routing, regex, and _resolve_source."""

from unittest.mock import patch, MagicMock

import pytest

from commands import dispatch, _NOTE_TAG_RE, _resolve_source
from session import Session
from client import AuthExpiredError


# ── _NOTE_TAG_RE ──


class TestNoteTagRegex:
    def test_add_tag(self):
        m = _NOTE_TAG_RE.match("s2 +t cheese, bread")
        assert m is not None
        assert m.group(1) == "2"
        assert m.group(2) == "+t"
        assert m.group(3) == "cheese, bread"

    def test_remove_tag(self):
        m = _NOTE_TAG_RE.match("s15 -t old_tag")
        assert m is not None
        assert m.group(1) == "15"
        assert m.group(2) == "-t"
        assert m.group(3) == "old_tag"

    def test_case_insensitive(self):
        m = _NOTE_TAG_RE.match("S3 +T mytag")
        assert m is not None
        assert m.group(1) == "3"

    def test_no_match_missing_space(self):
        assert _NOTE_TAG_RE.match("s2+t tag") is None

    def test_no_match_no_tags(self):
        assert _NOTE_TAG_RE.match("s2 +t") is None

    def test_no_match_plain_text(self):
        assert _NOTE_TAG_RE.match("hello world") is None


# ── _resolve_source() ──


class TestResolveSource:
    @patch("commands.client")
    def test_numeric_id_found(self, mock_client):
        mock_client.get_source.return_value = {"id": 5, "name": "foo"}
        assert _resolve_source("5") == 5

    @patch("commands.client")
    def test_numeric_id_not_found_falls_through_to_search(self, mock_client):
        mock_client.get_source.return_value = None
        mock_client.search_sources.return_value = []
        assert _resolve_source("999") is None

    @patch("commands.client")
    def test_name_search_exact_match(self, mock_client):
        mock_client.search_sources.return_value = [
            {"id": 1, "name": "Republic"},
            {"id": 2, "name": "The Republic"},
        ]
        # Exact match (case insensitive) should win
        assert _resolve_source("The Republic") == 2

    @patch("commands.client")
    def test_name_search_first_result(self, mock_client):
        mock_client.search_sources.return_value = [
            {"id": 10, "name": "Republic of Plato"},
        ]
        # No exact match, returns first result
        assert _resolve_source("rep") == 10

    @patch("commands.client")
    def test_no_results(self, mock_client):
        mock_client.search_sources.return_value = []
        assert _resolve_source("nonexistent") is None


# ── dispatch() routing ──


class TestDispatchRouting:
    def test_empty_input_returns_true(self):
        s = Session()
        assert dispatch("", s, "/tmp") is True
        assert dispatch("   ", s, "/tmp") is True

    def test_exit(self, capsys):
        s = Session()
        assert dispatch("exit", s, "/tmp") is False
        assert "Bye!" in capsys.readouterr().out

    def test_quit(self, capsys):
        s = Session()
        assert dispatch("quit", s, "/tmp") is False

    def test_exit_case_insensitive(self):
        s = Session()
        assert dispatch("EXIT", s, "/tmp") is False
        assert dispatch("Quit", s, "/tmp") is False

    def test_help(self, capsys):
        s = Session()
        assert dispatch("help", s, "/tmp") is True
        assert "Commands:" in capsys.readouterr().out

    @patch("commands.cmd_login")
    def test_login_dispatch(self, mock_login):
        s = Session()
        assert dispatch("login", s, "/tmp") is True
        mock_login.assert_called_once_with(s)

    @patch("commands.cmd_register")
    def test_register_dispatch(self, mock_register):
        s = Session()
        assert dispatch("register", s, "/tmp") is True
        mock_register.assert_called_once_with(s)

    @patch("commands.cmd_logout")
    def test_logout_dispatch(self, mock_logout):
        s = Session()
        assert dispatch("logout", s, "/tmp") is True
        mock_logout.assert_called_once_with(s)

    @patch("commands.client")
    def test_auth_gate_blocks_unauthenticated(self, mock_client, capsys):
        mock_client.is_authenticated.return_value = False
        s = Session()
        assert dispatch("b", s, "/tmp") is True
        assert "Not logged in" in capsys.readouterr().out

    @patch("commands.cmd_note")
    @patch("commands.client")
    def test_unrecognized_input_becomes_note(self, mock_client, mock_note):
        mock_client.is_authenticated.return_value = True
        s = Session()
        dispatch("this is a note", s, "/tmp")
        mock_note.assert_called_once_with(s, "this is a note")

    @patch("commands.cmd_browse")
    @patch("commands.client")
    def test_browse_commands(self, mock_client, mock_browse):
        mock_client.is_authenticated.return_value = True
        s = Session()
        for cmd in ("b", "browse", "ls", "B", "BROWSE", "LS"):
            dispatch(cmd, s, "/tmp")
        assert mock_browse.call_count == 6

    @patch("commands.cmd_s")
    @patch("commands.client")
    def test_s_command(self, mock_client, mock_s):
        mock_client.is_authenticated.return_value = True
        s = Session()
        dispatch("s 5", s, "/tmp")
        mock_s.assert_called_once_with(s, "5")

    @patch("commands.cmd_t")
    @patch("commands.client")
    def test_t_command(self, mock_client, mock_t):
        mock_client.is_authenticated.return_value = True
        s = Session()
        dispatch("t philosophy, plato", s, "/tmp")
        mock_t.assert_called_once_with(s, "philosophy, plato")

    @patch("commands.cmd_note_delete")
    @patch("commands.client")
    def test_del_command(self, mock_client, mock_del):
        mock_client.is_authenticated.return_value = True
        s = Session()
        dispatch("del 7", s, "/tmp")
        mock_del.assert_called_once_with(7)

    @patch("commands.client")
    def test_del_non_numeric(self, mock_client, capsys):
        mock_client.is_authenticated.return_value = True
        s = Session()
        dispatch("del abc", s, "/tmp")
        assert "Usage: del <note_id>" in capsys.readouterr().out


class TestAuthExpiredHandling:
    @patch("commands.client")
    def test_auth_expired_resets_session(self, mock_client, capsys):
        mock_client.is_authenticated.return_value = True
        mock_client.AuthExpiredError = AuthExpiredError
        mock_client.clear_token = MagicMock()

        s = Session()
        s.current_source_id = 5
        s.record_note(10)

        # Make _dispatch_data raise AuthExpiredError
        with patch("commands._dispatch_data", side_effect=AuthExpiredError("expired")):
            result = dispatch("b", s, "/tmp")

        assert result is True
        assert "Session expired" in capsys.readouterr().out
        mock_client.clear_token.assert_called_once()
        assert s.current_source_id is None
        assert s.last_note_id is None
