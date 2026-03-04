"""Markdown export generation for VS, VT, VA commands."""

import os
import re
from pathlib import Path

import client
from i18n import _, _n


def slugify(text: str, max_len: int = 40) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '_', s)
    return s[:max_len].strip('_')


def _ensure_export_dir(export_dir: str):
    Path(export_dir).mkdir(parents=True, exist_ok=True)


def _format_note_block(note: dict,
                       tags: list[dict] | None = None,
                       show_source: bool = False) -> str:
    lines = []
    meta_parts = [_("export.note_label", id=note['id']),
                  _("export.created", date=note['created_at'])]

    if note["locator_type"] and note["locator_value"]:
        if note["locator_type"] == "page":
            meta_parts.append(f"p{note['locator_value']}")
        else:
            meta_parts.append(f"t{note['locator_value']}")

    if tags is None:
        tags = client.get_tags_for_note(note["id"])
    if tags:
        tag_str = ", ".join(t["name"] for t in tags)
        meta_parts.append(_("export.tags", tags=tag_str))

    if show_source and note["source_id"]:
        src = client.get_source(note["source_id"])
        if src:
            meta_parts.append(_("export.source", name=src['name']))
            citation = client.build_citation(note["source_id"])
            if citation:
                meta_parts.append(_("export.citation", citation=citation))

    lines.append(" | ".join(meta_parts))
    lines.append("")
    lines.append(note["body"])
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def export_all(export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    notes = client.get_all_notes()

    lines = []
    for note in notes:
        lines.append(f"**#{note['id']}** | *{note['created_at']}*")
        lines.append("")
        lines.append(note["body"])
        lines.append("")
        lines.append("---")
        lines.append("")

    filepath = os.path.join(export_dir, "browse_all.md")
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_by_source(source_id: int, export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    src = client.get_source(source_id)
    if not src:
        raise ValueError(f"Source {source_id} not found")

    notes = client.get_notes_by_source(source_id)
    tags_map = client.get_tags_for_notes([n["id"] for n in notes])
    citation = client.build_citation(source_id)

    lines = [f"# {src['name']}", ""]
    if citation:
        lines += [f"*{citation}*", ""]
    count_str = _n("export.notes_count_one", "export.notes_count_other", len(notes))
    lines += [f"**{count_str}**", "", "---", ""]

    for note in notes:
        lines.append(_format_note_block(note, tags=tags_map.get(note["id"], [])))

    slug = slugify(src["name"])
    filename = f"source_{source_id}_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_by_tag(tag_id: int, export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    tag = client.get_tag(tag_id)
    if not tag:
        raise ValueError(f"Tag {tag_id} not found")

    notes = client.get_notes_by_tag(tag_id)
    tags_map = client.get_tags_for_notes([n["id"] for n in notes])

    count_str = _n("export.notes_count_one", "export.notes_count_other", len(notes))
    lines = [f"# {_('export.tag_heading', name=tag['name'])}", "",
             f"**{count_str}**", "", "---", ""]

    for note in notes:
        lines.append(_format_note_block(note, tags=tags_map.get(note["id"], []),
                                        show_source=True))

    slug = slugify(tag["name"])
    filename = f"tag_{tag_id}_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, notes


def export_search_results(query: str, notes: list[dict],
                          export_dir: str) -> str:
    _ensure_export_dir(export_dir)
    tags_map = client.get_tags_for_notes([n["id"] for n in notes])

    count_str = _n("export.notes_count_one", "export.notes_count_other", len(notes))
    lines = [f"# {_('export.search_heading', query=query)}", "",
             f"**{count_str}**", "", "---", ""]

    for note in notes:
        lines.append(_format_note_block(note, tags=tags_map.get(note["id"], []),
                                        show_source=True))

    slug = slugify(query)
    filename = f"search_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath


def export_by_author(author_last: str, author_first: str,
                     export_dir: str) -> tuple[str, list[dict]]:
    _ensure_export_dir(export_dir)
    sources = client.get_sources_by_author(author_last, author_first)

    all_notes = []
    lines = [f"# {_('export.author_heading', last=author_last, first=author_first)}", ""]

    for src in sources:
        citation = client.build_citation(src["id"])
        lines += [f"## {src['name']}", ""]
        if citation:
            lines += [f"*{citation}*", ""]

        notes = client.get_notes_by_source(src["id"])
        all_notes.extend(notes)
        tags_map = client.get_tags_for_notes([n["id"] for n in notes])

        for note in notes:
            lines.append(_format_note_block(note, tags=tags_map.get(note["id"], [])))

    count_str = _("export.notes_sources_count", notes=len(all_notes), sources=len(sources))
    lines.insert(2, f"**{count_str}**")
    lines.insert(3, "")

    slug = slugify(f"{author_last}_{author_first}")
    filename = f"author_{slug}.md"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))
    return filepath, all_notes
