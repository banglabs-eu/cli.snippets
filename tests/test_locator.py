"""Tests for locator.py — parse_locator()."""

from locator import parse_locator


class TestPageTokens:
    def test_p_simple(self):
        body, loc_type, loc_value = parse_locator("some note p32")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "32"

    def test_pp_range(self):
        body, loc_type, loc_value = parse_locator("some note pp. 10-15")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "10-15"

    def test_pp_range_no_dot(self):
        body, loc_type, loc_value = parse_locator("some note pp32-35")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "32-35"

    def test_case_insensitive(self):
        body, loc_type, loc_value = parse_locator("some note P32")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "32"

    def test_p_dot(self):
        body, loc_type, loc_value = parse_locator("some note p.5")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "5"

    def test_trailing_whitespace(self):
        body, loc_type, loc_value = parse_locator("some note p32   ")
        assert body == "some note"
        assert loc_type == "page"
        assert loc_value == "32"


class TestTimeTokens:
    def test_minutes_seconds(self):
        body, loc_type, loc_value = parse_locator("some note t0:32")
        assert body == "some note"
        assert loc_type == "time"
        assert loc_value == "0:32"

    def test_hours_minutes_seconds(self):
        body, loc_type, loc_value = parse_locator("some note t01:02:03")
        assert body == "some note"
        assert loc_type == "time"
        assert loc_value == "01:02:03"

    def test_case_insensitive(self):
        body, loc_type, loc_value = parse_locator("some note T1:23:45")
        assert body == "some note"
        assert loc_type == "time"
        assert loc_value == "1:23:45"

    def test_trailing_whitespace(self):
        body, loc_type, loc_value = parse_locator("some note t0:32  ")
        assert body == "some note"
        assert loc_type == "time"
        assert loc_value == "0:32"


class TestNoMatch:
    def test_plain_text(self):
        body, loc_type, loc_value = parse_locator("just a plain note")
        assert body == "just a plain note"
        assert loc_type is None
        assert loc_value is None

    def test_token_in_middle(self):
        """Token must be at the end — middle occurrences are not matched."""
        body, loc_type, loc_value = parse_locator("see p32 for details")
        # p32 is followed by more text, so the regex won't match it at the end
        # The regex requires the token at the very end
        assert loc_type is None

    def test_token_at_start_no_body(self):
        """Token with no preceding body text — regex requires leading \\s+."""
        body, loc_type, loc_value = parse_locator("p32")
        assert body == "p32"
        assert loc_type is None
        assert loc_value is None

    def test_empty_string(self):
        body, loc_type, loc_value = parse_locator("")
        assert body == ""
        assert loc_type is None
        assert loc_value is None

    def test_whitespace_only(self):
        body, loc_type, loc_value = parse_locator("   ")
        assert loc_type is None
        assert loc_value is None
