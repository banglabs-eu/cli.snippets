"""Shared fixtures for SnippetsCLI tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from session import Session


@pytest.fixture
def session():
    """Fresh Session instance."""
    return Session()


def make_response(status_code: int = 200, json_data=None, text: str = "") -> httpx.Response:
    """Build a fake httpx.Response with the given status and body."""
    kwargs = dict(
        status_code=status_code,
        request=httpx.Request("GET", "http://test"),
    )
    if json_data is not None:
        kwargs["json"] = json_data
    else:
        kwargs["text"] = text
    return httpx.Response(**kwargs)


@pytest.fixture
def mock_httpx_client():
    """Return a MagicMock that behaves like httpx.Client."""
    return MagicMock(spec=httpx.Client)
