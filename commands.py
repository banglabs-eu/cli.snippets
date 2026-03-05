"""Command implementations for Snippets CLI."""

import os
import re
import shutil
import subprocess

from prompt_toolkit import prompt

import getpass

import cache
import client
import export
import i18n
import offline
from i18n import _, _n
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
    print(_("cmd.help.text"))


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

    parts = [_("cmd.note.saved", id=note_id)]
    if session.current_source_id:
        src = client.get_source(session.current_source_id)
        if src:
            parts.append(_("cmd.note.linked_to", name=src["name"]))
    if loc_type:
        parts.append(f"{loc_type}={loc_value}")
    print(" | ".join(parts))


# ─── s <name_or_id> (set source) ───

def cmd_s(session: Session, arg: str):
    arg = arg.strip()
    if not arg:
        sources = client.get_all_sources()
        if sources:
            print(_("cmd.s.sources_header"))
            for src in sources:
                marker = "*" if src["id"] == session.current_source_id else " "
                print(f"  {marker} {src['id']}. {src['name']}")
        else:
            print(_("cmd.s.no_sources"))
        if session.current_source_id:
            src = client.get_source(session.current_source_id)
            if src:
                citation = client.build_citation(session.current_source_id)
                print(_("cmd.s.current", name=src["name"], id=src["id"]))
                if citation:
                    print(f"  {citation}")
        else:
            print(_("cmd.s.no_source_set"))
        return

    if arg.lower() in ("clear", "none"):
        session.current_source_id = None
        print(_("cmd.s.cleared"))
        return

    source_id = _resolve_source(arg)
    if source_id is None:
        print(_("cmd.s.not_found", name=arg))
        return

    session.current_source_id = source_id
    src = client.get_source(source_id)
    print(_("cmd.s.source_set", name=src["name"], id=source_id))

    sourceless = client.get_sourceless_notes(session.session_note_ids)
    if sourceless:
        client.bulk_update_note_source(sourceless, source_id)
        print(_n("cmd.s.linked_one", "cmd.s.linked_other", len(sourceless)))


# ─── s<id> +t / -t (add/remove tags on a note) ───

def cmd_note_add_tags(note_id: int, tags_str: str):
    note = client.get_note(note_id)
    if not note:
        print(_("cmd.note.not_found", id=note_id))
        return
    names = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not names:
        print(_("cmd.tags.none_specified"))
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
        print(_("cmd.note.not_found", id=note_id))
        return
    names = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not names:
        print(_("cmd.tags.none_specified"))
        return
    removed = []
    for name in names:
        tag = client.get_tag_by_name(name)
        if tag:
            client.remove_tag_from_note(note_id, tag["id"])
            removed.append(name.lower())
        else:
            print(_("cmd.tag.not_found", name=name))
    if removed:
        print(f"#{note_id} -t {', '.join(removed)}")


# ─── e <id> (edit a note) ───

def cmd_edit(note_id: int):
    note = client.get_note(note_id)
    if not note:
        print(_("cmd.note.not_found", id=note_id))
        return
    try:
        new_body = prompt(_("cmd.edit.prompt"), default=note["body"])
    except (EOFError, KeyboardInterrupt):
        print(_("cmd.cancelled"))
        return
    new_body = new_body.strip()
    if not new_body:
        print(_("cmd.edit.empty"))
        return
    if new_body == note["body"]:
        print(_("cmd.edit.no_changes"))
        return
    client.update_note_body(note_id, new_body)
    print(_("cmd.edit.updated", id=note_id))


# ─── del <id> (delete a note) ───

def cmd_note_delete(note_id: int):
    note = client.get_note(note_id)
    if not note:
        print(_("cmd.note.not_found", id=note_id))
        return
    ok = client.delete_note(note_id)
    if ok:
        print(f"{_('cmd.del.deleted', id=note_id)}\n{note['body']}")


# ─── t <tags> (tag last note) ───

def cmd_t(session: Session, tags_str: str):
    if session.last_note_id is None:
        print(_("cmd.t.no_note"))
        return
    cmd_note_add_tags(session.last_note_id, tags_str)


# ─── b (browse all notes) ───

def cmd_browse(export_dir: str):
    filepath, notes = export.export_all(export_dir)
    if not notes:
        print(_("cmd.browse.no_notes"))
        return
    _open_file(filepath)


# ─── ns <name> (new source for session) ───

def cmd_ns(session: Session, arg: str):
    name = arg.strip()
    if not name:
        print(_("cmd.ns.usage"))
        return

    source_id = _resolve_source(name)
    if source_id:
        session.current_source_id = source_id
        src = client.get_source(source_id)
        print(_("cmd.s.source_set", name=src["name"], id=source_id))
        return

    source_id = cmd_nse(prefilled_name=name)
    if source_id:
        session.current_source_id = source_id
        print(_("cmd.nse.source_set", id=source_id))


# ─── nse (source entry interview - the ONLY interactive mode) ───

def cmd_nse(prefilled_name: str | None = None) -> int | None:
    print(_("cmd.nse.title"))

    if prefilled_name:
        name = prefilled_name
        print(_("cmd.nse.source_title") + name)
    else:
        try:
            name = prompt(_("cmd.nse.source_title")).strip()
        except (EOFError, KeyboardInterrupt):
            print(_("cmd.cancelled"))
            return None
        if not name:
            print(_("cmd.cancelled"))
            return None

    # Source type
    types = client.get_source_types()
    print(_("cmd.nse.source_types"))
    for t in types:
        print(f"  {t['id']}. {t['name']}")
    try:
        type_input = prompt(_("cmd.nse.source_type_prompt"),
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

    def ask(key: str, completer=None) -> str | None:
        try:
            val = prompt(_("cmd.nse.field_prompt", field=_(key)),
                        completer=completer).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return val or None

    year = ask("cmd.nse.year")
    url = ask("cmd.nse.url")
    accessed_date = ask("cmd.nse.accessed_date")
    edition = ask("cmd.nse.edition")
    pages = ask("cmd.nse.pages")
    extra_notes = ask("cmd.nse.extra_notes")

    pub_name = ask("cmd.nse.publisher_name", completer=PublisherCompleter())
    publisher_id = None
    if pub_name:
        pub_city = ask("cmd.nse.publisher_city", completer=PublisherCityCompleter())
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
    print(_("cmd.nse.source_created", id=source_id, name=name))

    print(_("cmd.nse.add_authors"))
    order = 0
    while True:
        try:
            last = prompt(_("cmd.nse.author_last", n=order+1),
                         completer=AuthorLastNameCompleter()).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not last:
            break
        try:
            first = prompt(_("cmd.nse.author_first", n=order+1),
                          completer=AuthorFirstNameCompleter()).strip()
        except (EOFError, KeyboardInterrupt):
            first = ""
        client.add_author(source_id, first, last, order)
        print(_("cmd.nse.author_added", last=last, first=first))
        order += 1

    citation = client.build_citation(source_id)
    if citation:
        print(_("cmd.nse.citation", citation=citation))

    return source_id


# ─── vs <name_or_id> (view by source) ───

def cmd_vs(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print(_("cmd.vs.usage"))
        return
    source_id = _resolve_source(arg)
    if source_id is None:
        print(_("cmd.vs.not_found", name=arg))
        return
    filepath, notes = export.export_by_source(source_id, export_dir)
    print(_("cmd.export.info", path=filepath, count=len(notes)))
    _open_file(filepath)


# ─── vt <tag> (view by tag) ───

def cmd_vt(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print(_("cmd.vt.usage"))
        return
    tag = client.get_tag_by_name(arg)
    if not tag:
        print(_("cmd.vt.not_found", name=arg))
        return
    filepath, notes = export.export_by_tag(tag["id"], export_dir)
    print(_("cmd.export.info", path=filepath, count=len(notes)))
    _open_file(filepath)


# ─── va <Last, First> (view by author) ───

def cmd_va(export_dir: str, arg: str):
    arg = arg.strip()
    if not arg:
        print(_("cmd.va.usage"))
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
        print(_("cmd.va.not_found", name=arg))
        return
    print(_("cmd.export.info", path=filepath, count=len(notes)))
    _open_file(filepath)


# ─── find <query> (search notes by text) ───

def cmd_find(export_dir: str, query: str):
    query = query.strip()
    if not query:
        print(_("cmd.find.usage"))
        return
    notes = client.search_notes(query)
    if not notes:
        print(_("cmd.find.no_results", query=query))
        return
    filepath = export.export_search_results(query, notes, export_dir)
    print(_n("cmd.find.found_one", "cmd.find.found_other", len(notes), query=query))
    _open_file(filepath)


# ─── stadd <name> (add source type) ───

def cmd_stadd(arg: str):
    name = arg.strip()
    if not name:
        print(_("cmd.stadd.usage"))
        return
    try:
        tid = client.create_source_type(name)
        print(_("cmd.stadd.created", id=tid, name=name))
    except client.ConflictError:
        print(_("cmd.stadd.exists", name=name))


# ─── auth commands ───

def cmd_login(session: Session):
    try:
        username = input(_("cmd.login.username")).strip()
        password = getpass.getpass(_("cmd.login.password"))
    except (EOFError, KeyboardInterrupt):
        print(f"\n{_('cmd.cancelled')}")
        return
    if not username or not password:
        print(_("cmd.cancelled"))
        return
    try:
        data = client.login(username, password)
        session.reset()
        print(_("cmd.login.success", username=data['username']))
        cache.refresh()
        _try_sync_after_login()
    except ValueError as e:
        print(_("cmd.login.failed", detail=e))


def cmd_register(session: Session):
    try:
        username = input(_("cmd.register.username")).strip()
        password = getpass.getpass(_("cmd.register.password"))
        confirm = getpass.getpass(_("cmd.register.confirm"))
        invite_code = input(_("cmd.register.invite_code")).strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{_('cmd.cancelled')}")
        return
    if not username or not password:
        print(_("cmd.cancelled"))
        return
    if password != confirm:
        print(_("cmd.password_mismatch"))
        return
    try:
        data = client.register(username, password, invite_code)
        session.reset()
        print(_("cmd.register.success", username=data['username']))
    except client.ConflictError:
        print(_("cmd.register.taken"))
    except ValueError as e:
        print(_("cmd.register.failed", detail=e))


def cmd_change_password():
    try:
        current = getpass.getpass(_("cmd.passwd.current"))
        new_pw = getpass.getpass(_("cmd.passwd.new"))
        confirm = getpass.getpass(_("cmd.passwd.confirm"))
    except (EOFError, KeyboardInterrupt):
        print(f"\n{_('cmd.cancelled')}")
        return
    if not current or not new_pw:
        print(_("cmd.cancelled"))
        return
    if new_pw != confirm:
        print(_("cmd.password_mismatch"))
        return
    try:
        client.change_password(current, new_pw)
        print(_("cmd.passwd.success"))
    except ValueError as e:
        print(_("cmd.passwd.failed", detail=e))


def cmd_invite():
    try:
        code = client.create_invite_code()
        print(_("cmd.invite.code", code=code))
    except client.BackendError:
        print(_("cmd.invite.failed"))
    except Exception as e:
        detail = str(e)
        if "403" in detail:
            print(_("cmd.invite.admin_only"))
        else:
            raise


def cmd_invites():
    try:
        codes = client.list_invite_codes()
    except Exception as e:
        detail = str(e)
        if "403" in detail:
            print(_("cmd.invites.admin_only"))
            return
        raise
    if not codes:
        print(_("cmd.invites.none"))
        return
    for c in codes:
        status = _("cmd.invites.used", id=c['used_by']) if c.get("used_by") else _("cmd.invites.available")
        print(f"  {c['code']}  ({status})")


def cmd_whoami():
    data = client.me()
    print(data["username"])


def cmd_logout(session: Session):
    client.logout()
    session.reset()
    print(_("cmd.logout.success"))


# ─── lang ───

def cmd_lang(arg: str):
    arg = arg.strip()
    if not arg:
        print(_("lang.current", lang=i18n.get_lang()))
        return
    try:
        i18n.set_lang(arg)
        print(_("lang.changed", lang=arg))
    except ValueError:
        available = ", ".join(i18n.available_langs())
        print(_("lang.invalid", code=arg, available=available))


# ─── sync ───

def _try_sync_after_login():
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


# ─── offline commands ───

def cmd_note_offline(session: Session, text: str):
    text = text.strip()
    if not text:
        return
    body, loc_type, loc_value = parse_locator(text)
    local_id = session.offline_store.add_note(
        body,
        source_name=session.current_source_name,
        locator_type=loc_type,
        locator_value=loc_value,
    )
    parts = [_("cmd.note.saved_offline", n=local_id)]
    if session.current_source_name:
        parts.append(_("cmd.note.linked_to", name=session.current_source_name))
    if loc_type:
        parts.append(f"{loc_type}={loc_value}")
    print(" | ".join(parts))


def cmd_s_offline(session: Session, arg: str):
    arg = arg.strip()
    if not arg:
        if session.current_source_name:
            print(_("cmd.s.current_offline", name=session.current_source_name))
        else:
            print(_("cmd.s.no_source_set"))
        return
    if arg.lower() in ("clear", "none"):
        session.current_source_name = None
        print(_("cmd.s.cleared"))
        return
    session.current_source_name = arg
    print(_("cmd.s.source_set_offline", name=arg))


def cmd_t_offline(session: Session, tags_str: str):
    names = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not names:
        print(_("cmd.tags.none_specified"))
        return
    if not session.offline_store.add_tags_to_last(names):
        print(_("cmd.t.no_note"))
        return
    print(f"+t {', '.join(n.lower() for n in names)}")


# ─── command parser ───

_NOTE_TAG_RE = re.compile(r'^s(\d+)\s+([+-]t)\s+(.+)$', re.IGNORECASE)


def dispatch(user_input: str, session: Session, export_dir: str) -> bool:
    """Parse and dispatch a command. Returns False if should exit."""
    stripped = user_input.strip()
    if not stripped:
        return True

    cmd = stripped.upper()

    if cmd in ("EXIT", "QUIT"):
        print(_("cmd.bye"))
        return False

    if cmd == "HELP":
        cmd_help()
        return True

    # Language command — no login required
    parts_lang = stripped.split(None, 1)
    if parts_lang[0].upper() == "LANG":
        cmd_lang(parts_lang[1] if len(parts_lang) > 1 else "")
        return True

    # Offline mode — limited commands
    if session.offline_mode:
        return _dispatch_offline(stripped, cmd, session)

    # Auth commands — always available
    if cmd == "LOGIN":
        cmd_login(session)
        return True
    if cmd == "REGISTER":
        cmd_register(session)
        return True
    if cmd == "LOGOUT":
        cmd_logout(session)
        return True

    # All other commands require authentication
    if not client.is_authenticated():
        print(_("cmd.not_logged_in"))
        return True

    if cmd in ("CHANGE_PASSWORD", "PASSWD"):
        cmd_change_password()
        return True
    if cmd == "WHOAMI":
        cmd_whoami()
        return True
    if cmd == "INVITE":
        cmd_invite()
        return True
    if cmd == "INVITES":
        cmd_invites()
        return True

    try:
        return _dispatch_data(stripped, cmd, session, export_dir)
    except client.AuthExpiredError:
        print(_("cmd.session_expired"))
        client.clear_token()
        session.reset()
        return True


def _dispatch_offline(stripped: str, cmd: str, session: Session) -> bool:
    """Dispatch commands in offline mode."""
    parts = stripped.split(None, 1)
    prefix = parts[0].upper()
    arg = parts[1] if len(parts) > 1 else ""

    if prefix == "S":
        cmd_s_offline(session, arg)
    elif prefix == "T":
        cmd_t_offline(session, arg)
    else:
        cmd_note_offline(session, stripped)

    return True


def _dispatch_data(stripped: str, cmd: str, session: Session, export_dir: str) -> bool:
    """Dispatch data commands (requires authentication)."""
    if cmd in ("B", "BROWSE", "LS"):
        cmd_browse(export_dir)
        return True

    if cmd == "NSE":
        source_id = cmd_nse()
        if source_id:
            session.current_source_id = source_id
            print(_("cmd.nse.source_set", id=source_id))
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
    elif prefix in ("FIND", "F"):
        cmd_find(export_dir, arg)
    elif prefix == "STADD":
        cmd_stadd(arg)
    elif prefix in ("E", "EDIT"):
        if not arg.isdigit():
            print(_("cmd.edit.usage"))
        else:
            cmd_edit(int(arg))
    elif prefix == "DEL":
        if not arg.isdigit():
            print(_("cmd.del.usage"))
        else:
            cmd_note_delete(int(arg))
    else:
        # No recognized command — treat entire line as a note
        cmd_note(session, stripped)

    return True
