"""Command implementations for Snippets CLI."""

import os
import re
import shutil
import subprocess

from prompt_toolkit import prompt

import client
import export
from locator import parse_locator
from session import Session
from completers import (
    SourceTypeCompleter, PublisherCompleter, PublisherCityCompleter,
    AuthorLastNameCompleter, AuthorFirstNameCompleter,
)


def _find_pager() -> list[str]:
    for cmd in ("batcat", "bat"):
        if shutil.which(cmd):
            return [cmd, "--language", "markdown", "--style", "plain", "--paging", "always"]
    if shutil.which("less"):
        return ["less", "-R"]
    return []


def _open_file(filepath: str):
    editor = os.environ.get("EDITOR", "")
    if editor:
        subprocess.run([editor, filepath])
    elif os.isatty(0):
        pager = _find_pager()
        if pager:
            subprocess.run(pager + [filepath])
        else:
            with open(filepath, "r") as f:
                print(f.read())
    else:
        with open(filepath, "r") as f:
            print(f.read())


def _resolve_source(arg: str) -> int | None:
    if arg.isdigit():
        src = client.get_source(int(arg))
        if src:
            return src["id"]
    matches = client.search_sources(arg)
    exact = [m for m in matches if m["name"].lower() == arg.lower()]
    if exact:
        return exact[0]["id"]
    if matches:
        return matches[0]["id"]
    return None


# ─── help ───

def cmd_help():
    print("""
Commands:
  <text>             Just type — any unrecognized input is saved as a note
  s <name_or_id>     Set session source (Tab to autocomplete)
  s clear            Unset source — future notes have no source
  s<id> +t <tags>    Add tag(s) to note (e.g. s2 +t cheese, bread)
  s<id> -t <tags>    Remove tag(s) from note (e.g. s2 -t cheese)
  del <id>           Delete a note (e.g. del 5)
  t <tags>           Tag the last note (Tab to autocomplete)
  b                  Browse all notes (rendered markdown)
  ns <name>          New source for session (reuse existing or create via nse)
  nse                Source entry interview (MLA-ish fields)
  vs <name_or_id>    View/export notes by source
  vt <tag>           View/export notes by tag
  va <Last, First>   View/export notes by author
  stadd <name>       Add a new source type
  help               Show this help
  exit               Quit

Locator tokens (append to end of note):
  p32       Page 32        pp. 10-15   Pages 10-15
  t1:23:45  Time 1:23:45

Example session:
  > ns The Republic
  > The cave allegory is profound p514
  > t philosophy, epistemology
  > s2 +t plato
  > vs The Republic
  > b
""")


# ─── note creation (no command prefix) ───

def cmd_note(session: Session, text: str):
    text = text.strip()
    if not text:
        return

    body, loc_type, loc_value = parse_locator(text)

    note_id = client.create_note(
        body,
        source_id=session.current_source_id,
        locator_type=loc_type,
        locator_value=loc_value,
    )
    session.record_note(note_id)

    parts = [f"Saved note #{note_id}"]
    if session.current_source_id:
        src = client.get_source(session.current_source_id)
        if src:
            parts.append(f'linked to "{src["name"]}"')
    if loc_type:
        parts.append(f"{loc_type}={loc_value}")
    print(" | ".join(parts))


# ─── s <name_or_id> (set source) ───

def cmd_s(session: Session, arg: str):
    arg = arg.strip()
    if not arg:
        if session.current_source_id:
            src = client.get_source(session.current_source_id)
            if src:
                citation = client.build_citation(session.current_source_id)
                print(f'Current source: "{src["name"]}" (id:{src["id"]})')
                if citation:
                    print(f"  {citation}")
                return
        print("No source set. Use: s <name_or_id>")
        return

    if arg.lower() in ("clear", "none"):
        session.current_source_id = None
        print("Source cleared. Future notes will have no source.")
        return

    source_id = _resolve_source(arg)
    if source_id is None:
        print(f'Source "{arg}" not found. Use ns <name> to create one.')
        return

    session.current_source_id = source_id
    src = client.get_source(source_id)
    print(f'Source set: "{src["name"]}" (id:{source_id})')

    sourceless = client.get_sourceless_notes(session.session_note_ids)
    if sourceless:
        client.bulk_update_note_source(sourceless, source_id)
        print(f"Linked {len(sourceless)} previous session note(s).")


# ─── s<id> +t / -t (add/remove tags on a note) ───

def cmd_note_add_tags(note_id: int, tags_str: str):
    note = client.get_note(note_id)
    if not note:
        print(f"Note #{note_id} not found.")
        return
    names = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not names:
        print("No tags specified.")
        return
    added = []
    for name in names:
        tag_id = client.get_or_create_tag(name)
        client.add_tag_to_note(note_id, tag_id)
        added.append(name.lower())
    print(f"#{note_id} +t {', '.join(added)}")


def cmd_note_remove_tags(note_id: int, tags_str: str):
    note = client.get_note(note_id)
    if not note:
        print(f"Note #{note_id} not found.")
        return
    names = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not names:
        print("No tags specified.")
        return
    removed = []
    for name in names:
        tag = client.get_tag_by_name(name)
        if tag:
            client.remove_tag_from_note(note_id, tag["id"])
            removed.append(name.lower())
        else:
            print(f"Tag '{name}' not found.")
    if removed:
        print(f"#{note_id} -t {', '.join(removed)}")


# ─── del <id> (delete a note) ───

def cmd_note_delete(note_id: int):
    note = client.get_note(note_id)
    if not note:
        print(f"Note #{note_id} not found.")
        return
    ok = client.delete_note(note_id)
    if ok:
        print(f"Deleted note #{note_id}.")


# ─── t <tags> (tag last note) ───

def cmd_t(session: Session, tags_str: str):
    if session.last_note_id is None:
        print("No note created this session yet.")
        return
    cmd_note_add_tags(session.last_note_id, tags_str)


# ─── b (browse all notes) ───

def cmd_browse(export_dir: str):
    filepath, notes = export.export_all(export_dir)
    if not notes:
        print("No notes yet.")
        return
    _open_file(filepath)


# ─── ns <name> (new source for session) ───

def cmd_ns(session: Session, arg: str):
    name = arg.strip()
    if not name:
        print("Usage: ns <source_name>")
        return

    source_id = _resolve_source(name)
    if source_id:
        session.current_source_id = source_id
        src = client.get_source(source_id)
        print(f'Source set: "{src["name"]}" (id:{source_id})')
        return

    source_id = cmd_nse(prefilled_name=name)
    if source_id:
        session.current_source_id = source_id
        print(f'Source set: id:{source_id}')


# ─── nse (source entry interview - the ONLY interactive mode) ───

def cmd_nse(prefilled_name: str | None = None) -> int | None:
    print("=== Source Entry Interview ===")

    if prefilled_name:
        name = prefilled_name
        print(f"Source title: {name}")
    else:
        try:
            name = prompt("Source title: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Cancelled.")
            return None
        if not name:
            print("Cancelled.")
            return None

    # Source type
    types = client.get_source_types()
    print("Source types:")
    for t in types:
        print(f"  {t['id']}. {t['name']}")
    try:
        type_input = prompt("Source type (name or #, Enter to skip): ",
                           completer=SourceTypeCompleter()).strip()
    except (EOFError, KeyboardInterrupt):
        type_input = ""

    source_type_id = None
    if type_input:
        if type_input.isdigit():
            st = client.get_source_type(int(type_input))
            if st:
                source_type_id = st["id"]
        else:
            for t in types:
                if t["name"].lower() == type_input.lower():
                    source_type_id = t["id"]
                    break

    def ask(label: str, completer=None) -> str | None:
        try:
            val = prompt(f"{label} (Enter to skip): ", completer=completer).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return val or None

    year = ask("Year/date")
    url = ask("URL")
    accessed_date = ask("Accessed date")
    edition = ask("Edition")
    pages = ask("Pages (range)")
    extra_notes = ask("Extra notes")

    pub_name = ask("Publisher name", completer=PublisherCompleter())
    publisher_id = None
    if pub_name:
        pub_city = ask("Publisher city", completer=PublisherCityCompleter())
        publisher_id = client.get_or_create_publisher(pub_name, pub_city)

    source_id = client.create_source(
        name,
        source_type_id=source_type_id,
        year=year, url=url,
        accessed_date=accessed_date,
        edition=edition, pages=pages,
        extra_notes=extra_notes,
        publisher_id=publisher_id,
    )
    print(f"Source created: #{source_id} - {name}")

    print("Add authors (empty last name to stop):")
    order = 0
    while True:
        try:
            last = prompt(f"  Author {order+1} last name: ",
                         completer=AuthorLastNameCompleter()).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not last:
            break
        try:
            first = prompt(f"  Author {order+1} first name: ",
                          completer=AuthorFirstNameCompleter()).strip()
        except (EOFError, KeyboardInterrupt):
            first = ""
        client.add_author(source_id, first, last, order)
        print(f"    Added: {last}, {first}")
        order += 1

    citation = client.build_citation(source_id)
    if citation:
        print(f"Citation: {citation}")

    return source_id


# ─── vs <name_or_id> (view by source) ───

def cmd_vs(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print("Usage: vs <source_name_or_id>")
        return
    source_id = _resolve_source(arg)
    if source_id is None:
        print(f'Source "{arg}" not found.')
        return
    filepath, notes = export.export_by_source(source_id, export_dir)
    print(f"Export: {filepath} ({len(notes)} notes)")
    _open_file(filepath)


# ─── vt <tag> (view by tag) ───

def cmd_vt(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print("Usage: vt <tag_name>")
        return
    tag = client.get_tag_by_name(arg)
    if not tag:
        print(f'Tag "{arg}" not found.')
        return
    filepath, notes = export.export_by_tag(tag["id"], export_dir)
    print(f"Export: {filepath} ({len(notes)} notes)")
    _open_file(filepath)


# ─── va <Last, First> (view by author) ───

def cmd_va(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print("Usage: va <Last, First>")
        return
    if "," in arg:
        parts = arg.split(",", 1)
        author_last = parts[0].strip()
        author_first = parts[1].strip()
    else:
        author_last = arg
        author_first = ""

    filepath, notes = export.export_by_author(author_last, author_first, export_dir)
    if not notes:
        print(f'No notes found for author "{arg}".')
        return
    print(f"Export: {filepath} ({len(notes)} notes)")
    _open_file(filepath)


# ─── stadd <name> (add source type) ───

def cmd_stadd(arg: str):
    name = arg.strip()
    if not name:
        print("Usage: stadd <type_name>")
        return
    try:
        tid = client.create_source_type(name)
        print(f"Source type created: #{tid} - {name}")
    except client.ConflictError:
        print(f"Source type '{name}' already exists.")


# ─── command parser ───

_NOTE_TAG_RE = re.compile(r'^s(\d+)\s+([+-]t)\s+(.+)$', re.IGNORECASE)


def dispatch(user_input: str, session: Session, export_dir: str) -> bool:
    """Parse and dispatch a command. Returns False if should exit."""
    stripped = user_input.strip()
    if not stripped:
        return True

    cmd = stripped.upper()

    if cmd in ("EXIT", "QUIT"):
        print("Bye!")
        return False

    if cmd == "HELP":
        cmd_help()
        return True

    if cmd in ("B", "BROWSE"):
        cmd_browse(export_dir)
        return True

    if cmd == "NSE":
        source_id = cmd_nse()
        if source_id:
            session.current_source_id = source_id
            print(f'Source set: id:{source_id}')
        return True

    # s<id> +t / -t
    m = _NOTE_TAG_RE.match(stripped)
    if m:
        note_id = int(m.group(1))
        op = m.group(2).lower()
        tags_str = m.group(3)
        if op == "+t":
            cmd_note_add_tags(note_id, tags_str)
        else:
            cmd_note_remove_tags(note_id, tags_str)
        return True

    # Commands with arguments: split on first space
    parts = stripped.split(None, 1)
    prefix = parts[0].upper()
    arg = parts[1] if len(parts) > 1 else ""

    if prefix == "S":
        cmd_s(session, arg)
    elif prefix == "T":
        cmd_t(session, arg)
    elif prefix == "NS":
        cmd_ns(session, arg)
    elif prefix == "VS":
        cmd_vs(export_dir, arg)
    elif prefix == "VT":
        cmd_vt(export_dir, arg)
    elif prefix == "VA":
        cmd_va(export_dir, arg)
    elif prefix == "STADD":
        cmd_stadd(arg)
    elif prefix == "DEL":
        if not arg.isdigit():
            print("Usage: del <note_id>")
        else:
            cmd_note_delete(int(arg))
    else:
        # No recognized command — treat entire line as a note
        cmd_note(session, stripped)

    return True
