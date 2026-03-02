"""Interactive snippet picker for viewing/tagging notes after export."""

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import clear

import db
from completers import TagCompleter, NoteTagCompleter


def _note_row_str(conn, note: dict, selected: bool) -> str:
    prefix = ">" if selected else " "
    loc = ""
    if note["locator_type"] and note["locator_value"]:
        if note["locator_type"] == "page":
            loc = f"p{note['locator_value']}"
        else:
            loc = f"t{note['locator_value']}"
    loc = loc.ljust(12)

    body_preview = note["body"].replace("\n", " ")[:80]

    tags = db.get_tags_for_note(conn, note["id"])
    tag_str = ", ".join(t["name"] for t in tags)
    if len(tag_str) > 30:
        tag_str = tag_str[:27] + "..."

    created = str(note["created_at"])[:16] if note["created_at"] else ""
    return f"{prefix} #{note['id']:<5} {created}  {loc} {body_preview:<80}  [{tag_str}]"


def run_picker(conn, notes: list[dict],
               export_fn=None):
    """Run interactive picker. export_fn() regenerates/opens the export."""
    if not notes:
        print("No notes to display.")
        return

    idx = 0

    def render():
        clear()
        print("=== Snippet Picker ===")
        print("Up/Down: j/k | a: add tag | r: remove tag | o: regenerate export | q: quit")
        print("-" * 120)
        for i, note in enumerate(notes):
            print(_note_row_str(conn, note, selected=(i == idx)))
        print("-" * 120)
        print(f"Selected: Note #{notes[idx]['id']}")

    render()

    while True:
        try:
            key = prompt("picker> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if key in ("q", "quit"):
            break
        elif key in ("j", "down"):
            idx = min(idx + 1, len(notes) - 1)
        elif key in ("k", "up"):
            idx = max(idx - 1, 0)
        elif key == "a":
            _add_tags(conn, notes[idx])
        elif key == "r":
            _remove_tags(conn, notes[idx])
        elif key == "o":
            if export_fn:
                export_fn()
                print("Export regenerated and opened.")
        else:
            print(f"Unknown key: {key}. Use j/k/a/r/o/q.")
            continue

        render()


def _add_tags(conn, note: dict):
    try:
        tag_input = prompt("Add tag(s) [comma-separated]: ",
                          completer=TagCompleter(conn))
    except (EOFError, KeyboardInterrupt):
        return

    if not tag_input.strip():
        return

    names = [t.strip() for t in tag_input.split(",") if t.strip()]
    for name in names:
        tag_id = db.get_or_create_tag(conn, name)
        db.add_tag_to_note(conn, note["id"], tag_id)
        print(f"  + tag '{name}' added to note #{note['id']}")


def _remove_tags(conn, note: dict):
    current_tags = db.get_tags_for_note(conn, note["id"])
    if not current_tags:
        print("  No tags on this note.")
        return

    print(f"  Current tags: {', '.join(t['name'] for t in current_tags)}")
    try:
        tag_input = prompt("Remove tag(s) [comma-separated]: ",
                          completer=NoteTagCompleter(conn, note["id"]))
    except (EOFError, KeyboardInterrupt):
        return

    if not tag_input.strip():
        return

    names = [t.strip().lower() for t in tag_input.split(",") if t.strip()]
    for name in names:
        tag = db.get_tag_by_name(conn, name)
        if tag:
            db.remove_tag_from_note(conn, note["id"], tag["id"])
            print(f"  - tag '{name}' removed from note #{note['id']}")
        else:
            print(f"  Tag '{name}' not found.")
