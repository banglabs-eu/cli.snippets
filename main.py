#!/usr/bin/env python3
"""Snippets CLI - A note-taking REPL with PostgreSQL storage."""

import os
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

import client
from session import Session
from commands import dispatch
from completers import ReplCompleter

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "./exports")


def main():
    client.init(BACKEND_URL)
    session = Session()
    completer = ReplCompleter()

    history_dir = Path.home() / ".snippets_cli"
    history_dir.mkdir(exist_ok=True)
    history = FileHistory(str(history_dir / "history"))

    kb = KeyBindings()

    @kb.add("c-j")
    def _insert_newline(event):
        event.current_buffer.insert_text("\n")

    print("Snippets CLI ready. Type 'help' for commands.")

    while True:
        try:
            src_label = ""
            if session.current_source_id:
                src = client.get_source(session.current_source_id)
                if src:
                    src_label = f' [{src["name"][:20]}]'

            user_input = prompt(f"snippets{src_label}> ", history=history,
                                completer=completer, complete_while_typing=False,
                                key_bindings=kb)
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not dispatch(user_input, session, EXPORT_DIR):
            break


if __name__ == "__main__":
    main()
