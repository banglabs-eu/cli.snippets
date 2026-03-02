"""prompt_toolkit completers backed by database queries."""

import re
from prompt_toolkit.completion import Completer, Completion
import db


class SourceCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if text:
            sources = db.search_sources(self.conn, text)
        else:
            sources = db.get_recent_sources(self.conn)
        for s in sources:
            yield Completion(s["name"], start_position=-len(text),
                             display_meta=f'id:{s["id"]}')


class TagCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        # Handle comma-separated: complete only the last segment
        if "," in text:
            parts = text.rsplit(",", 1)
            prefix = parts[1].strip()
            already_typed = len(parts[1]) - len(parts[1].lstrip())
            start_pos = -len(prefix)
        else:
            prefix = text
            start_pos = -len(text)

        if prefix:
            tags = db.search_tags(self.conn, prefix)
        else:
            tags = db.get_recent_tags(self.conn)
        for t in tags:
            yield Completion(t["name"], start_position=start_pos)


class NoteTagCompleter(Completer):
    """Completer limited to tags on a specific note."""
    def __init__(self, conn, note_id):
        self.conn = conn
        self.note_id = note_id

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if "," in text:
            prefix = text.rsplit(",", 1)[1].strip()
            start_pos = -len(prefix)
        else:
            prefix = text
            start_pos = -len(text)

        tags = db.get_tags_for_note(self.conn, self.note_id)
        for t in tags:
            if t["name"].startswith(prefix.lower()):
                yield Completion(t["name"], start_position=start_pos)


class AuthorCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if text:
            authors = db.search_authors(self.conn, text)
        else:
            authors = db.get_recent_authors(self.conn)
        seen = set()
        for a in authors:
            display = f'{a["last_name"]}, {a["first_name"]}'
            if display not in seen:
                seen.add(display)
                yield Completion(display, start_position=-len(text),
                                 display_meta=f'id:{a["id"]}')


class SourceTypeCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip().lower()
        types = db.get_source_types(self.conn)
        for t in types:
            if t["name"].lower().startswith(text):
                yield Completion(t["name"], start_position=-len(document.text_before_cursor))


class PublisherCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        pubs = db.search_publishers(self.conn, text) if text else []
        for p in pubs:
            meta = f'({p["city"]})' if p["city"] else ""
            yield Completion(p["name"], start_position=-len(text), display_meta=meta)


class PublisherCityCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        cities = db.search_publisher_cities(self.conn, text) if text else []
        for c in cities:
            yield Completion(c, start_position=-len(text))


class AuthorLastNameCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        names = db.search_author_last_names(self.conn, text) if text else []
        for n in names:
            yield Completion(n, start_position=-len(text))


class AuthorFirstNameCompleter(Completer):
    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        names = db.search_author_first_names(self.conn, text) if text else []
        for n in names:
            yield Completion(n, start_position=-len(text))


# Pattern for s<id> +t / -t
_NOTE_TAG_PREFIX = re.compile(r'^s(\d+)\s+[+-]t\s+', re.IGNORECASE)

# Commands that complete sources
_SOURCE_CMDS = {"s", "ns", "vs"}
# Commands that complete tags
_TAG_CMDS = {"t", "vt"}
# Commands that complete authors
_AUTHOR_CMDS = {"va"}


class ReplCompleter(Completer):
    """Context-aware completer for the main REPL prompt."""

    def __init__(self, conn):
        self.conn = conn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()
        if not stripped:
            return

        # s<id> +t tag1, tag2  — complete tags after the +t/-t
        m = _NOTE_TAG_PREFIX.match(stripped)
        if m:
            after = stripped[m.end():]
            # complete the last comma-separated segment
            if "," in after:
                prefix = after.rsplit(",", 1)[1].strip()
            else:
                prefix = after
            yield from self._complete_tags(prefix)
            return

        # Split into command + argument
        parts = stripped.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in _SOURCE_CMDS:
            yield from self._complete_sources(arg)
        elif cmd in _TAG_CMDS:
            # t supports comma-separated
            if "," in arg:
                prefix = arg.rsplit(",", 1)[1].strip()
            else:
                prefix = arg
            yield from self._complete_tags(prefix)
        elif cmd in _AUTHOR_CMDS:
            yield from self._complete_authors(arg)

    def _complete_sources(self, prefix):
        if prefix:
            sources = db.search_sources(self.conn, prefix)
        else:
            sources = db.get_recent_sources(self.conn)
        for s in sources:
            yield Completion(s["name"], start_position=-len(prefix),
                             display_meta=f'id:{s["id"]}')

    def _complete_tags(self, prefix):
        if prefix:
            tags = db.search_tags(self.conn, prefix)
        else:
            tags = db.get_recent_tags(self.conn)
        for t in tags:
            yield Completion(t["name"], start_position=-len(prefix))

    def _complete_authors(self, prefix):
        if prefix:
            authors = db.search_authors(self.conn, prefix)
        else:
            authors = db.get_recent_authors(self.conn)
        seen = set()
        for a in authors:
            display = f'{a["last_name"]}, {a["first_name"]}'
            if display not in seen:
                seen.add(display)
                yield Completion(display, start_position=-len(prefix),
                                 display_meta=f'id:{a["id"]}')
