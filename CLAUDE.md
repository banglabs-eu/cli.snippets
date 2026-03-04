# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

SnippetsCLI is a terminal REPL for taking Markdown notes with source citations, tags, and page/time locators. It talks to a separate FastAPI backend ([SnippetsBackend](https://github.com/banglabs-eu/SnippetsBackend)) over HTTP — the CLI has no direct database access.

## Running

```bash
# Backend (separate repo at ../SnippetsBackend)
docker compose up --build

# CLI
pip install -r requirements.txt
cp .env.example .env    # set BACKEND_URL and EXPORT_DIR
python3 main.py
```

There are no tests, linter, or build step in this repo.

## Architecture

```
main.py  →  REPL loop (prompt_toolkit), health check, network error handling
commands.py  →  dispatch(input) parses commands, calls client.*, returns bool (False = exit)
client.py  →  httpx.Client wrapper; every function maps to a backend REST endpoint
session.py  →  In-memory state: current_source_id, last_note_id, session_note_ids
completers.py  →  Context-aware Tab completion (sources, tags, authors, publishers)
export.py  →  Generates Markdown files in EXPORT_DIR, opened via bat/less/EDITOR
locator.py  →  Regex parser for page (p32, pp. 10-15) and time (t1:23:45) tokens at end of note text
```

`db.py` is a legacy direct-psycopg2 layer kept for reference — it is not imported anywhere.

## Key Data Flow

1. User types text at prompt → `dispatch()` in commands.py
2. Unrecognized input → `cmd_note()` → `parse_locator()` strips page/time token → `client.create_note()`
3. Recognized prefix (s, t, ns, vs, vt, va, del, etc.) → corresponding `cmd_*` function
4. All data operations go through `client.py` → HTTP to backend → PostgreSQL

## Important Patterns

- **Session note relinking**: When a source is set via `cmd_s`, all sourceless notes from the current session are bulk-linked to it (`client.get_sourceless_notes` + `client.bulk_update_note_source`).
- **Auth token**: JWT stored at `~/.snippets_cli/token`. Loaded on every request via `_headers()`. `AuthExpiredError` (401) clears token and resets session. `logout` calls `POST /logout` to revoke the token server-side before deleting locally.
- **`BackendError`**: Maps HTTP 5xx — caught in the main loop, printed without crashing.
- **`ConflictError`**: Maps HTTP 409 — used for duplicate usernames, source types, etc.
- **`get_tags_for_notes`** returns JSON with string keys; `client.py` converts to `dict[int, list[dict]]`.
- **`get_sourceless_notes`** is a POST (not GET) because it sends a body with note_ids.
- **Only interactive mode**: `nse` (source entry interview) — everything else is single-line inline.
- **Multiline input**: Ctrl+J inserts a newline. Shift+Enter also works in terminals with CSI u / kitty keyboard protocol (e.g. WezTerm) — mapped via `ANSI_SEQUENCES["\x1b[13;2u"]` in main.py.
- **Session reset**: `session.reset()` clears source/note state on login, logout, register, and auth expiry to prevent cross-user data leaks.
- **Startup checks**: Health check (3s timeout) verifies backend is reachable. If a token exists, `client.me()` validates it and shows the username; expired tokens are cleared immediately.
- **Network errors**: Caught in the main loop — prompt shows `[offline]` label, commands print a message and return to prompt without crashing.

## Command Dispatch (commands.py)

`dispatch()` checks in order:
1. exit/quit → return False
2. help/login/register/logout → always available
3. lang → available without auth (language switching)
4. Auth gate: remaining commands require `client.is_authenticated()`
5. `_dispatch_data()`: regex match `s<id> +t/-t` → tag ops, then prefix match (S, T, NS, VS, VT, VA, STADD, DEL, B/BROWSE/LS, NSE) → else treat as note text

## Internationalization (i18n)

- **`i18n.py`** — Translation module. `init()` loads language at startup; `_(key, **kwargs)` returns translated string with `str.format()` interpolation; `_n(key_one, key_other, count)` handles plurals.
- **`i18n/*.json`** — Flat dot-namespaced translation files (en, de, fr, es, it, pt). Keys follow `module.context.name` pattern (e.g. `cmd.note.saved`, `export.tags`). Variables use `{name}` placeholders.
- **Language priority**: persisted file `~/.snippets_cli/language` > `SNIPPETS_LANG` env var > `"en"`.
- **Fallback chain**: current language → English → raw key. Missing keys in any translation automatically fall back to English.
- **Commands stay in English** — only output text (help, errors, prompts, status messages) is translated.
- **`lang` command**: `lang` shows current language, `lang <code>` switches and persists. Available before login.
- **Adding a new language**: Create `i18n/<code>.json` with translated keys. Missing keys fall back to English automatically.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `BACKEND_URL` | `http://localhost:5000` | Backend API base URL |
| `EXPORT_DIR` | `./exports` | Markdown export output directory |
| `SNIPPETS_LANG` | `en` | Display language (en, de, fr, es, it, pt) |
