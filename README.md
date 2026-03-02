# Snippets CLI

A terminal-based note-taking REPL that stores Markdown snippets in PostgreSQL with source citations, tags, locator references, and Markdown export.

The CLI talks to a REST backend [SnippetsBackend](https://github.com/banglabs-eu/SnippetsBackend) — start the backend before running the CLI.

## Setup

### 1. Start the backend

See [SnippetsBackend](https://github.com/banglabs-eu/SnippetsBackend) for setup. Once running, it listens on `http://localhost:8000` by default.

### 2. Install CLI dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Copy `.env.example` to `.env`:

```
BACKEND_URL=http://localhost:8000   # URL of the running SnippetsBackend
EXPORT_DIR=./exports                # Directory for generated Markdown exports
```

## Run

```bash
python3 main.py
```

## Commands

Everything is typed inline at the prompt. The only interactive mode is `nse` (source entry interview).

| Command | Description |
|---------|-------------|
| `<text>` | Just type — any unrecognized input is saved as a note |
| `s <name_or_id>` | Set session source (Tab to autocomplete) |
| `s clear` / `s none` | Unset source — future notes have no source |
| `s` | Show current source |
| `s<id> +t <tags>` | Add tag(s) to a note (e.g. `s2 +t cheese, bread`) |
| `s<id> -t <tags>` | Remove tag(s) from a note (e.g. `s2 -t cheese`) |
| `t <tags>` | Tag the last note created this session |
| `b` | Browse all notes in order (rendered via bat/less) |
| `ns <name>` | New source for session (reuse existing or create via nse) |
| `nse` | Source entry interview — MLA-ish fields with autocomplete |
| `vs <name_or_id>` | View/export notes by source |
| `vt <tag>` | View/export notes by tag |
| `va <Last, First>` | View/export notes by author |
| `stadd <name>` | Add a new source type |
| `help` | Show all commands |
| `exit` / `quit` | Quit |

### Autocomplete (Tab)

The REPL provides Tab-completion in context:

- `s <Tab>` — source names
- `t <Tab>` — tag names (comma-separated supported)
- `s<id> +t <Tab>` — tag names
- `vs <Tab>` — source names
- `vt <Tab>` — tag names
- `va <Tab>` — author names
- `ns <Tab>` — source names
- Inside `nse`: author last/first names, publisher names, publisher cities, source types

### Locator Tokens

Append to the end of a note to automatically parse page/time references:

- `p32` — Page 32
- `pp. 10-15` — Pages 10-15
- `t1:23:45` — Timestamp 1:23:45

The token is stripped from the stored body and shown in export metadata.

## Example Session

```
$ python3 main.py
Snippets CLI ready. Type 'help' for commands.

snippets> Knowledge is justified true belief p42
Saved note #1 | page=42

snippets> The cave allegory suggests we perceive shadows p514
Saved note #2 | page=514

snippets> t philosophy, epistemology
#2 +t philosophy, epistemology

snippets> s1 +t ancient, plato
#1 +t ancient, plato

snippets> ns The Republic
=== Source Entry Interview ===
Source title: The Republic
Source types:
  1. Book
  2. Article
  3. Magazine
  4. YouTube Video
  5. Other
Source type (name or #, Enter to skip): 1
Year/date (Enter to skip): 380 BCE
URL (Enter to skip):
Accessed date (Enter to skip):
Edition (Enter to skip): Revised
Pages (range) (Enter to skip):
Extra notes (Enter to skip):
Publisher name (Enter to skip): Penguin Classics
Publisher city (Enter to skip): London
Source created: #1 - The Republic
Add authors (empty last name to stop):
  Author 1 last name: Plato
  Author 1 first name:
    Added: Plato,
  Author 2 last name:
Citation: Plato. *The Republic*. Book. Revised ed. London: Penguin Classics, 380 BCE.
Source set: id:1

snippets [The Republic]> s The Republic
Source set: "The Republic" (id:1)
Linked 2 previous session note(s).

snippets [The Republic]> Philosopher kings must rule pp. 10-15
Saved note #3 | linked to "The Republic" | page=10-15

snippets [The Republic]> Interesting discussion of Book VII t0:32
Saved note #4 | linked to "The Republic" | time=0:32

snippets [The Republic]> t political-theory
#4 +t political-theory

snippets [The Republic]> s
Current source: "The Republic" (id:1)
  Plato. *The Republic*. Book. Revised ed. London: Penguin Classics, 380 BCE.

snippets [The Republic]> s clear
Source cleared. Future notes will have no source.

snippets> A note with no source
Saved note #5

snippets> b
(opens all notes in bat/less, rendered as markdown)

snippets> vs The Republic
Export: ./exports/source_1_the_republic.md (4 notes)
(opens in bat/less)

snippets> vt philosophy
Export: ./exports/tag_1_philosophy.md (1 notes)
(opens in bat/less)

snippets> va Plato
Export: ./exports/author_plato_.md (4 notes)
(opens in bat/less)

snippets> exit
Bye!
```

## Schema

See `schema.sql` (or [SnippetsBackend/schema.sql](../SnippetsBackend/schema.sql)) for the full PostgreSQL schema. Tables:

- `notes` — Markdown snippets with optional source link and locator
- `sources` — Bibliographic sources (books, articles, etc.)
- `source_types` — Enumeration of source types (Book, Article, etc.)
- `source_authors` — Authors linked to sources with ordering
- `source_publishers` — Publisher normalization
- `tags` — Tag names (unique, lowercase)
- `note_tags` — Many-to-many join table

## Architecture

```
main.py        REPL entry point — initialises HTTP client, runs the prompt loop
client.py      HTTP client — mirrors the db API, talks to SnippetsBackend
session.py     Session state (current source, note tracking)
commands.py    Command implementations + dispatch parser
export.py      Markdown export generation
completers.py  prompt_toolkit completers (REPL + NSE fields)
picker.py      Interactive snippet picker for viewing/tagging notes
locator.py     Locator token parsing (page/time references)
schema.sql     PostgreSQL DDL + seed data (reference copy)
```
