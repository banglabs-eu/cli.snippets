"""Locator token parsing for notes (page/time references)."""

import re


# Page patterns: p32, p 32, p.32, pp. 32-35, pp32-35
_PAGE_RE = re.compile(
    r'\s+(pp?\.?\s*\d+(?:\s*-\s*\d+)?)\s*$',
    re.IGNORECASE,
)

# Time patterns: t00:00, t0:32, t01:02:03
_TIME_RE = re.compile(
    r'\s+(t\d{1,2}:\d{2}(?::\d{2})?)\s*$',
    re.IGNORECASE,
)


def parse_locator(text: str) -> tuple[str, str | None, str | None]:
    """Parse locator token from end of text.

    Returns (cleaned_body, locator_type, locator_value).
    """
    stripped = text.rstrip()

    # Try time first (more specific)
    m = _TIME_RE.search(stripped)
    if m:
        token = m.group(1)
        body = stripped[:m.start()].rstrip()
        value = token[1:]  # strip leading 't'
        return body, "time", value

    # Try page
    m = _PAGE_RE.search(stripped)
    if m:
        token = m.group(1)
        body = stripped[:m.start()].rstrip()
        # Normalize: extract just the numbers
        value = re.sub(r'^pp?\.?\s*', '', token, flags=re.IGNORECASE).strip()
        return body, "page", value

    return text, None, None
