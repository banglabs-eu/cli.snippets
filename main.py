#!/usr/bin/env python3
"""Snippets CLI - A note-taking REPL with PostgreSQL storage."""

import os
from pathlib import Path

from dotenv import load_dotenv
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

import db
from session import Session
from commands import dispatch
from completers import ReplCompleter

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/snippets")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "./exports")


def main():
    conn = db.init_db(DATABASE_URL)
    session = Session()
    completer = ReplCompleter(conn)

    history_dir = Path.home() / ".snippets_cli"
    history_dir.mkdir(exist_ok=True)
    history = FileHistory(str(history_dir / "history"))

    print("Snippets CLI ready. Type 'help' for commands.")

    while True:
        try:
            src_label = ""
            if session.current_source_id:
                src = db.get_source(conn, session.current_source_id)
                if src:
                    src_label = f' [{src["name"][:20]}]'

            user_input = prompt(f"snippets{src_label}> ", history=history,
                                completer=completer, complete_while_typing=False)
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not dispatch(user_input, conn, session, EXPORT_DIR):
            break

    conn.close()


if __name__ == "__main__":
    main()
