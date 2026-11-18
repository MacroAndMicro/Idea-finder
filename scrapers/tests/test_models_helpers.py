"""IF-57: edge cases for the scrapers.models normalisation helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scrapers.models import content_hash, from_unix, html_to_text

# --- from_unix -------------------------------------------------------------


def test_from_unix_none_is_none() -> None:
    assert from_unix(None) is None


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        (0, datetime(1970, 1, 1, tzinfo=UTC)),
        (1_700_000_000, datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)),
        (1.5, datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=1.5)),
    ],
)
def test_from_unix_returns_utc_aware_datetime(ts: float, expected: datetime) -> None:
    result = from_unix(ts)
    assert result == expected
    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_from_unix_zero_is_epoch_not_none() -> None:
    # 0 is falsy; it must still be treated as a real timestamp.
    assert from_unix(0) == datetime(1970, 1, 1, tzinfo=UTC)


# --- html_to_text ----------------------------------------------------------


@pytest.mark.parametrize("value", ["", "   ", "<p></p>", "<br/><br>", "<div> \t </div>"])
def test_html_to_text_empty_inputs_are_none(value: str) -> None:
    assert html_to_text(value) is None


def test_html_to_text_none_is_none() -> None:
    assert html_to_text(None) is None


def test_html_to_text_decodes_entities_after_stripping_tags() -> None:
    # Escaped markup is text, not a tag: it must survive as literal characters.
    assert html_to_text("&lt;script&gt; &quot;q&quot; &#39;s&#39; a&amp;b") == (
        "<script> \"q\" 's' a&b"
    )


def test_html_to_text_nbsp_collapses_to_space() -> None:
    assert html_to_text("a&nbsp;&nbsp;b \t c") == "a b c"


def test_html_to_text_nested_inline_tags() -> None:
    assert html_to_text("<p>use <b><i>this</i> flag</b> now</p>") == "use this flag now"


def test_html_to_text_block_boundaries_do_not_fuse_words() -> None:
    html = "<div><ul><li>alpha</li><li>beta</li></ul></div><h2>Title</h2>tail"
    assert html_to_text(html) == "alpha\nbeta\nTitle\ntail"


def test_html_to_text_breaks_and_paragraph_attributes() -> None:
    assert html_to_text('a<br/>b<BR>c<p class="x">d</p>') == "a\nb\nc\nd"


def test_html_to_text_pre_code_keeps_lines() -> None:
    html = '<pre class="lang-py"><code>x = 1\n    y = 2\n</code></pre>after'
    # Lines survive; leading indentation is collapsed by design (text for the LLM).
    assert html_to_text(html) == "x = 1\ny = 2\nafter"


def test_html_to_text_does_not_treat_lookalike_tags_as_blocks() -> None:
    # <b>, <pre> vs <p>, <param>: only real block tags may introduce a newline.
    assert html_to_text("a<b>b</b>c") == "abc"


# --- content_hash ----------------------------------------------------------


def test_content_hash_none_equals_empty() -> None:
    assert content_hash(None, None) == content_hash("", "")


def test_content_hash_whitespace_only_equals_empty() -> None:
    assert content_hash("   ", "\n\t ") == content_hash(None, None)


def test_content_hash_is_deterministic_hex_sha256() -> None:
    h = content_hash("Title", "Body")
    assert h == content_hash("Title", "Body")
    assert len(h) == 64
    int(h, 16)


def test_content_hash_normalises_case_and_whitespace() -> None:
    messy = content_hash("Broken  CSV", "export\n fails")
    assert messy == content_hash("broken csv", "export fails")


def test_content_hash_different_text_differs() -> None:
    assert content_hash("export fails", None) != content_hash("import fails", None)
    assert content_hash("a", "b") != content_hash("a", "c")
