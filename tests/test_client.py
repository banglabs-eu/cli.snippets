"""Tests for client.py — HTTP client layer."""

from unittest.mock import patch, MagicMock

import httpx
import pytest

import client
from client import (
    _check,
    AuthExpiredError,
    ConflictError,
    BackendError,
)
from tests.conftest import make_response


# ── _check() ──


class TestCheck:
    def test_200_passes_through(self):
        resp = make_response(200, json_data={"ok": True})
        assert _check(resp) is resp

    def test_401_raises_auth_expired(self):
        resp = make_response(401, json_data={"detail": "Token expired"})
        with pytest.raises(AuthExpiredError, match="Token expired"):
            _check(resp)

    def test_409_raises_conflict(self):
        resp = make_response(409, text="duplicate")
        with pytest.raises(ConflictError):
            _check(resp)

    def test_500_raises_backend_error(self):
        resp = make_response(500)
        with pytest.raises(BackendError, match="500"):
            _check(resp)

    def test_502_raises_backend_error(self):
        resp = make_response(502)
        with pytest.raises(BackendError, match="502"):
            _check(resp)

    def test_400_raises_http_status_error(self):
        resp = make_response(400, json_data={"detail": "bad"})
        with pytest.raises(httpx.HTTPStatusError):
            _check(resp)


# ── health() ──


class TestHealth:
    @patch.object(client, "_client")
    def test_healthy(self, mock_client):
        mock_client.get.return_value = make_response(200)
        assert client.health() is True

    @patch.object(client, "_client")
    def test_unhealthy(self, mock_client):
        mock_client.get.return_value = make_response(503)
        assert client.health() is False


# ── login() ──


class TestLogin:
    @patch("client.save_token")
    @patch.object(client, "_client")
    def test_success(self, mock_client, mock_save):
        mock_client.post.return_value = make_response(
            200, json_data={"token": "abc123", "username": "alice"}
        )
        data = client.login("alice", "pass")
        assert data["username"] == "alice"
        mock_save.assert_called_once_with("abc123")

    @patch.object(client, "_client")
    def test_invalid_credentials(self, mock_client):
        mock_client.post.return_value = make_response(
            401, json_data={"detail": "Unauthorized"}
        )
        with pytest.raises(ValueError, match="Invalid username or password"):
            client.login("alice", "wrong")


# ── register() ──


class TestRegister:
    @patch("client.save_token")
    @patch.object(client, "_client")
    def test_success(self, mock_client, mock_save):
        mock_client.post.return_value = make_response(
            200, json_data={"token": "tok", "username": "bob"}
        )
        data = client.register("bob", "secret")
        assert data["username"] == "bob"
        mock_save.assert_called_once_with("tok")

    @patch.object(client, "_client")
    def test_duplicate_username(self, mock_client):
        mock_client.post.return_value = make_response(409, text="conflict")
        with pytest.raises(ConflictError, match="Username already taken"):
            client.register("bob", "secret")

    @patch.object(client, "_client")
    def test_bad_request(self, mock_client):
        mock_client.post.return_value = make_response(
            400, json_data={"detail": "Password too short"}
        )
        with pytest.raises(ValueError, match="Password too short"):
            client.register("bob", "x")


# ── logout() ──


class TestLogout:
    @patch("client.clear_token")
    @patch("client._headers", return_value={"Authorization": "Bearer tok"})
    @patch.object(client, "_client")
    def test_clears_token_on_success(self, mock_client, _hdr, mock_clear):
        mock_client.post.return_value = make_response(200)
        client.logout()
        mock_clear.assert_called_once()

    @patch("client.clear_token")
    @patch("client._headers", return_value={})
    @patch.object(client, "_client")
    def test_clears_token_on_failure(self, mock_client, _hdr, mock_clear):
        mock_client.post.side_effect = Exception("network error")
        client.logout()
        mock_clear.assert_called_once()
