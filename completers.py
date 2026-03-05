"""prompt_toolkit completers backed by the API client (or local cache when offline)."""

import re
from prompt_toolkit.completion import Completer, Completion
import cache
import client

# Set to True by main.py when running in offline mode
offline_mode = False


class SourceCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if text:
            sources = client.search_sources(text)
        else:
            sources = client.get_recent_sources()
        for s in sources:
            yield Completion(s["name"], start_position=-len(text),
                             display_meta=f'id:{s["id"]}')


class TagCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        # Handle comma-separated: complete only the last segment
        if "," in text:
            parts = text.rsplit(",", 1)
            prefix = parts[1].strip()
            start_pos = -len(prefix)
        else:
            prefix = text
            start_pos = -len(text)

        if prefix:
            tags = client.search_tags(prefix)
        else:
            tags = client.get_recent_tags()
        for t in tags:
            yield Completion(t["name"], start_position=start_pos)


class NoteTagCompleter(Completer):
    """Completer limited to tags on a specific note."""
    def __init__(self, note_id):
        self.note_id = note_id

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if "," in text:
            prefix = text.rsplit(",", 1)[1].strip()
            start_pos = -len(prefix)
        else:
            prefix = text
            start_pos = -len(text)

        tags = client.get_tags_for_note(self.note_id)
        for t in tags:
            if t["name"].startswith(prefix.lower()):
                yield Completion(t["name"], start_position=start_pos)


class AuthorCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        if text:
            authors = client.search_authors(text)
        else:
            authors = client.get_recent_authors()
        seen = set()
        for a in authors:
            display = f'{a["last_name"]}, {a["first_name"]}'
            if display not in seen:
                seen.add(display)
                yield Completion(display, start_position=-len(text),
                                 display_meta=f'id:{a["id"]}')


class SourceTypeCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip().lower()
        types = client.get_source_types()
        for t in types:
            if t["name"].lower().startswith(text):
                yield Completion(t["name"], start_position=-len(document.text_before_cursor))


class PublisherCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        pubs = client.search_publishers(text) if text else []
        for p in pubs:
            meta = f'({p["city"]})' if p["city"] else ""
            yield Completion(p["name"], start_position=-len(text), display_meta=meta)


class PublisherCityCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        cities = client.search_publisher_cities(text) if text else []
        for c in cities:
            yield Completion(c, start_position=-len(text))


class AuthorLastNameCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        names = client.search_author_last_names(text) if text else []
        for n in names:
            yield Completion(n, start_position=-len(text))


class AuthorFirstNameCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        names = client.search_author_first_names(text) if text else []
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


_CMDS_UNAUTH = ["help", "login", "register", "lang", "exit", "quit"]
_CMDS_AUTH = _CMDS_UNAUTH + [
    "logout", "change_password", "passwd", "whoami", "invite", "invites",
    "s", "t", "ns", "nse", "vs", "vt", "va", "stadd", "del",
    "find", "f", "e", "edit", "b", "browse", "ls",
]


class ReplCompleter(Completer):
    """Context-aware completer for the main REPL prompt."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()
        if not stripped:
            return

        # If user is typing the first word (no spaces), complete command names
        if " " not in stripped:
            word = stripped.lower()
            cmds = _CMDS_AUTH if client.is_authenticated() else _CMDS_UNAUTH
            for cmd in cmds:
                if cmd.startswith(word) and cmd != word:
                    yield Completion(cmd, start_position=-len(stripped))
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
        mod = cache if offline_mode else client
        if prefix:
            sources = mod.search_sources(prefix)
        else:
            sources = mod.get_recent_sources()
        for s in sources:
            yield Completion(s["name"], start_position=-len(prefix),
                             display_meta=f'id:{s["id"]}')

    def _complete_tags(self, prefix):
        mod = cache if offline_mode else client
        if prefix:
            tags = mod.search_tags(prefix)
        else:
            tags = mod.get_recent_tags()
        for t in tags:
            yield Completion(t["name"], start_position=-len(prefix))

    def _complete_authors(self, prefix):
        mod = cache if offline_mode else client
        if prefix:
            authors = mod.search_authors(prefix)
        else:
            authors = mod.get_recent_authors()
        seen = set()
        for a in authors:
            display = f'{a["last_name"]}, {a["first_name"]}'
            if display not in seen:
                seen.add(display)
                yield Completion(display, start_position=-len(prefix),
                                 display_meta=f'id:{a["id"]}')
