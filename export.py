"""Markdown export generation for VS, VT, VA commands."""

import os
import re
from pathlib import Path

import db


def slugify(text: str, max_len: int = 40) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '_', s)
    return s[:max_len].strip('_')


def _ensure_export_dir(export_dir: str):
    Path(export_dir).mkdir(parents=True, exist_ok=True)


def _format_note_block(conn, note: dict,
                       tags: list[dict] | None = None,
                       show_source: bool = False) -> str:
    lines = []
    meta_parts = [f"Note #{note['id']}", f"Created: {note['created_at']}"]

    if note["locator_type"] and note["locator_value"]:
        if note["locator_type"] == "page":
            meta_parts.append(f"p{note['locator_value']}")
        else:
            meta_parts.append(f"t{note['locator_value']}")

    if tags is None:
        tags = db.get_tags_for_note(conn, note["id"])
    if tags:
        tag_str = ", ".join(t["name"] for t in tags)
        meta_parts.append(f"Tags: {tag_str}")

    if show_source and note["source_id"]:
        src = db.get_source(conn, note["source_id"])
        if src:
            meta_parts.append(f"Source: {src['name']}")
            citation = db.build_citation(conn, note["source_id"])
            if citation:
                meta_parts.append(f"Citation: {citation}")

    lines.append(" | ".join(meta_parts))
    lines.append("")
    lines.append(note["body"])
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def export_all(conn, export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    notes = db.get_all_notes(conn)

    lines = []
    for note in notes:
        lines.append(f"*{note['created_at']}*")
        lines.append("")
        lines.append(note["body"])
        lines.append("")
        lines.append("---")
        lines.append("")

    filepath = os.path.join(export_dir, "browse_all.md")
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_by_source(conn, source_id: int, export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    src = db.get_source(conn, source_id)
    if not src:
        raise ValueError(f"Source {source_id} not found")

    notes = db.get_notes_by_source(conn, source_id)
    tags_map = db.get_tags_for_notes(conn, [n["id"] for n in notes])
    citation = db.build_citation(conn, source_id)

    lines = [f"# {src['name']}", ""]
    if citation:
        lines += [f"*{citation}*", ""]
    lines += [f"**{len(notes)} note(s)**", "", "---", ""]

    for note in notes:
        lines.append(_format_note_block(conn, note, tags=tags_map.get(note["id"], [])))

    slug = slugify(src["name"])
    filename = f"source_{source_id}_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_by_tag(conn, tag_id: int, export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    cur = conn.cursor()
    cur.execute("SELECT * FROM tags WHERE id = %s", (tag_id,))
    tag = cur.fetchone()
    if not tag:
        raise ValueError(f"Tag {tag_id} not found")

    notes = db.get_notes_by_tag(conn, tag_id)
    tags_map = db.get_tags_for_notes(conn, [n["id"] for n in notes])

    lines = [f"# Tag: {tag['name']}", "", f"**{len(notes)} note(s)**", "", "---", ""]

    for note in notes:
        lines.append(_format_note_block(conn, note, tags=tags_map.get(note["id"], []),
                                        show_source=True))

    slug = slugify(tag["name"])
    filename = f"tag_{tag_id}_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_by_author(conn, author_last: str, author_first: str,
                     export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    sources = db.get_sources_by_author(conn, author_last, author_first)

    all_notes = []
    lines = [f"# Author: {author_last}, {author_first}", ""]

    for src in sources:
        citation = db.build_citation(conn, src["id"])
        lines += [f"## {src['name']}", ""]
        if citation:
            lines += [f"*{citation}*", ""]

        notes = db.get_notes_by_source(conn, src["id"])
        all_notes.extend(notes)
        tags_map = db.get_tags_for_notes(conn, [n["id"] for n in notes])

        for note in notes:
            lines.append(_format_note_block(conn, note, tags=tags_map.get(note["id"], [])))

    lines.insert(2, f"**{len(all_notes)} note(s) across {len(sources)} source(s)**")
    lines.insert(3, "")

    slug = slugify(f"{author_last}_{author_first}")
    filename = f"author_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, all_notes
