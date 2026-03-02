"""HTTP client mirroring db.py — talks to the FastAPI backend."""

import httpx

_client: httpx.Client | None = None


class ConflictError(Exception):
    pass


def init(base_url: str):
    global _client
    _client = httpx.Client(base_url=base_url, timeout=30.0)


def _get() -> httpx.Client:
    if _client is None:
        raise RuntimeError("client not initialized; call client.init(base_url) first")
    return _client


def _check(response: httpx.Response) -> httpx.Response:
    if response.status_code == 409:
        raise ConflictError(response.text)
    response.raise_for_status()
    return response


# --- Notes ---

def create_note(body: str, source_id: int | None = None,
                locator_type: str | None = None, locator_value: str | None = None) -> int:
    r = _check(_get().post("/notes", json={
        "body": body,
        "source_id": source_id,
        "locator_type": locator_type,
        "locator_value": locator_value,
    }))
    return r.json()["id"]


def update_note_source(note_id: int, source_id: int):
    _check(_get().patch(f"/notes/{note_id}/source", json={"source_id": source_id}))


def get_note(note_id: int) -> dict | None:
    r = _get().get(f"/notes/{note_id}")
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def get_all_notes() -> list[dict]:
    r = _check(_get().get("/notes"))
    return r.json()


def get_notes_by_source(source_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"source_id": source_id}))
    return r.json()


def get_notes_by_tag(tag_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"tag_id": tag_id}))
    return r.json()


def get_notes_by_author(author_id: int) -> list[dict]:
    r = _check(_get().get("/notes", params={"author_id": author_id}))
    return r.json()


def get_sourceless_notes(note_ids: list[int]) -> list[int]:
    if not note_ids:
        return []
    r = _check(_get().post("/notes/sourceless-check", json={"note_ids": note_ids}))
    return r.json()


def bulk_update_note_source(note_ids: list[int], source_id: int):
    if not note_ids:
        return
    _check(_get().post("/notes/bulk-source", json={"note_ids": note_ids, "source_id": source_id}))


def delete_note(note_id: int):
    r = _get().delete(f"/notes/{note_id}")
    if r.status_code == 404:
        return False
    _check(r)
    return True


def get_tags_for_note(note_id: int) -> list[dict]:
    r = _check(_get().get(f"/notes/{note_id}/tags"))
    return r.json()


def add_tag_to_note(note_id: int, tag_id: int):
    _check(_get().post(f"/notes/{note_id}/tags", json={"tag_id": tag_id}))


def remove_tag_from_note(note_id: int, tag_id: int):
    _check(_get().delete(f"/notes/{note_id}/tags/{tag_id}"))


def get_tags_for_notes(note_ids: list[int]) -> dict[int, list[dict]]:
    if not note_ids:
        return {}
    r = _check(_get().post("/notes/tags/batch", json={"note_ids": note_ids}))
    return {int(k): v for k, v in r.json().items()}


# --- Sources ---

def create_source(name: str, source_type_id: int | None = None,
                  year: str | None = None, url: str | None = None,
                  accessed_date: str | None = None, edition: str | None = None,
                  pages: str | None = None, extra_notes: str | None = None,
                  publisher_id: int | None = None) -> int:
    r = _check(_get().post("/sources", json={
        "name": name,
        "source_type_id": source_type_id,
        "year": year,
        "url": url,
        "accessed_date": accessed_date,
        "edition": edition,
        "pages": pages,
        "extra_notes": extra_notes,
        "publisher_id": publisher_id,
    }))
    return r.json()["id"]


def get_source(source_id: int) -> dict | None:
    r = _get().get(f"/sources/{source_id}")
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def search_sources(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/sources/search", params={"q": prefix}))
    return r.json()


def get_recent_sources(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/sources/recent"))
    return r.json()


def get_all_sources() -> list[dict]:
    r = _check(_get().get("/sources"))
    return r.json()


def get_sources_by_author(author_last: str, author_first: str) -> list[dict]:
    r = _check(_get().get("/sources", params={"author_last": author_last, "author_first": author_first}))
    return r.json()


def build_citation(source_id: int) -> str:
    r = _check(_get().get(f"/sources/{source_id}/citation"))
    return r.json()["citation"]


def get_authors_for_source(source_id: int) -> list[dict]:
    r = _check(_get().get(f"/sources/{source_id}/authors"))
    return r.json()


def add_author(source_id: int, first_name: str, last_name: str, order: int) -> int:
    r = _check(_get().post(f"/sources/{source_id}/authors", json={
        "first_name": first_name,
        "last_name": last_name,
        "order": order,
    }))
    return r.json()["id"]


# --- Source Types ---

def get_source_types() -> list[dict]:
    r = _check(_get().get("/source-types"))
    return r.json()


def get_source_type(type_id: int) -> dict | None:
    r = _get().get(f"/source-types/{type_id}")
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def create_source_type(name: str) -> int:
    r = _check(_get().post("/source-types", json={"name": name}))
    return r.json()["id"]


# --- Publishers ---

def search_publishers(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/publishers/search", params={"q": prefix}))
    return r.json()


def search_publisher_cities(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/publishers/cities", params={"q": prefix}))
    return r.json()


def get_or_create_publisher(name: str, city: str | None = None) -> int:
    r = _check(_get().post("/publishers/get-or-create", json={"name": name, "city": city}))
    return r.json()["id"]


# --- Authors ---

def get_all_authors() -> list[dict]:
    r = _check(_get().get("/authors"))
    return r.json()


def get_recent_authors(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/authors/recent"))
    return r.json()


def search_authors(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/authors/search", params={"q": prefix}))
    return r.json()


def search_author_last_names(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/authors/last-names", params={"q": prefix}))
    return r.json()


def search_author_first_names(prefix: str, limit: int = 20) -> list[str]:
    r = _check(_get().get("/authors/first-names", params={"q": prefix}))
    return r.json()


# --- Tags ---

def get_or_create_tag(name: str) -> int:
    r = _check(_get().post("/tags/get-or-create", json={"name": name}))
    return r.json()["id"]


def get_tag(tag_id: int) -> dict | None:
    r = _get().get(f"/tags/{tag_id}")
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def get_tag_by_name(name: str) -> dict | None:
    r = _get().get("/tags/by-name", params={"name": name})
    if r.status_code == 404:
        return None
    _check(r)
    return r.json()


def search_tags(prefix: str, limit: int = 20) -> list[dict]:
    r = _check(_get().get("/tags/search", params={"q": prefix}))
    return r.json()


def get_all_tags() -> list[dict]:
    r = _check(_get().get("/tags"))
    return r.json()


def get_recent_tags(limit: int = 10) -> list[dict]:
    r = _check(_get().get("/tags/recent"))
    return r.json()
