#!/usr/bin/env python3
"""cli.Snippets - A note-taking REPL with PostgreSQL storage."""

import os
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

import httpx
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.input.vt100_parser import _IS_PREFIX_OF_LONGER_MATCH_CACHE
from prompt_toolkit.keys import Keys

import cache
import client
import completers as completers_mod
import i18n
import offline
from i18n import _

# Map Shift+Enter (kitty/CSI u protocol from WezTerm) to Ctrl+J
ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ
_IS_PREFIX_OF_LONGER_MATCH_CACHE.clear()
from session import Session
from commands import dispatch
from completers import ReplCompleter

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "./exports")


def _try_sync_offline():
    if not offline.has_offline_notes():
        return
    store = offline.OfflineStore()
    n = store.count()
    if n == 0:
        return
    print(_("main.offline_found", count=n))
    try:
        answer = input(_("main.sync_prompt")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if answer not in ("y", "yes"):
        return
    try:
        synced = offline.sync_offline_notes()
        print(_("main.sync_done", count=synced))
    except Exception as e:
        print(_("main.sync_failed", detail=e))


def main():
    i18n.init()
    client.init(BACKEND_URL)

    session = Session()

    try:
        client.health()
    except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError):
        print(_("main.backend_unreachable"))
        try:
            answer = input(_("main.offline_prompt")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_('main.bye')}")
            return
        if answer not in ("y", "yes"):
            return
        session.offline_mode = True
        session.offline_store = offline.OfflineStore()
        completers_mod.offline_mode = True
        cache.load()

    completer = ReplCompleter()

    history_dir = Path.home() / ".snippets_cli"
    history_dir.mkdir(exist_ok=True)
    history = FileHistory(str(history_dir / "history"))

    kb = KeyBindings()

    @kb.add("c-j")
    def _insert_newline(event):
        event.current_buffer.insert_text("\n")

    if session.offline_mode:
        n = session.offline_store.count()
        print(_("main.offline_ready", S=_("app.snippets")))
        if n:
            print(_("main.offline_pending", count=n))
    else:
        print(_("main.ready", S=_("app.snippets")))
        if client.is_authenticated():
            try:
                user = client.me()
                print(_("main.logged_in_as", username=user['username']))
                cache.refresh()
                _try_sync_offline()
            except client.AuthExpiredError:
                print(_("main.session_expired"))
                client.clear_token()
        else:
            print(_("main.not_logged_in"))

    while True:
        try:
            src_label = ""
            if session.offline_mode:
                if session.current_source_name:
                    src_label = f" [{session.current_source_name[:20]}]"
                src_label += f" [{_('main.offline')}]"
            else:
                try:
                    if session.current_source_id:
                        src = client.get_source(session.current_source_id)
                        if src:
                            src_label = f' [{src["name"][:20]}]'
                except (httpx.NetworkError, httpx.TimeoutException):
                    src_label = f" [{_('main.offline')}]"

            user_input = prompt(f"cli.{_('app.snippets')}{src_label}> ", history=history,
                                completer=completer, complete_while_typing=False,
                                key_bindings=kb)
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_('main.bye')}")
            break

        try:
            if not dispatch(user_input, session, EXPORT_DIR):
                break
        except (httpx.NetworkError, httpx.TimeoutException):
            print(_("main.backend_unreachable"))
            print(_("main.backend_check"))
        except client.BackendError as e:
            print(_("main.error", detail=e))


if __name__ == "__main__":
    main()
