from datetime import UTC, datetime

import pytest

from scrapers import config
from scrapers.models import RawSignal, content_hash, hash_author, html_to_text


def test_require_env_names_variable_not_value(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(config.MissingSecretError) as exc:
        config.require_env("GITHUB_TOKEN")
    assert "GITHUB_TOKEN" in str(exc.value)


def test_require_env_treats_blank_as_missing(monkeypatch):
    monkeypatch.setenv("STACKEXCHANGE_KEY", "   ")
    with pytest.raises(config.MissingSecretError):
        config.require_env("STACKEXCHANGE_KEY")


def test_require_env_error_never_contains_secret(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "super-secret-value")
    assert config.require_env("LLM_API_KEY") == "super-secret-value"
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(config.MissingSecretError) as exc:
        config.require_env("LLM_API_KEY")
    assert "super-secret-value" not in str(exc.value)


def test_user_agent_is_honest_default_and_overridable(monkeypatch):
    monkeypatch.delenv("SCRAPER_USER_AGENT", raising=False)
    assert config.user_agent().startswith("idea-finder-scrapers/")
    monkeypatch.setenv("SCRAPER_USER_AGENT", "idea-finder/test")
    assert config.user_agent() == "idea-finder/test"


def test_raw_signal_fills_content_hash_and_row():
    sig = RawSignal("hackernews", "1", "https://news.ycombinator.com/item?id=1", title="T",
                    body="B", source_created_at=datetime(2026, 11, 1, tzinfo=UTC))
    assert sig.content_hash == content_hash("T", "B")
    row = sig.to_row()
    assert row["source_created_at"] == "2026-11-01T00:00:00+00:00"
    assert set(row) == {
        "source_platform", "external_id", "url", "title", "body", "author_handle_hash",
        "score", "comment_count", "tags", "source_created_at", "content_hash",
    }


def test_raw_signal_rejects_unknown_platform():
    with pytest.raises(ValueError):
        RawSignal("twitter", "1", "https://x")


def test_hash_author_is_one_way_and_stable():
    h = hash_author("github", "Alice")
    assert h == hash_author("github", "alice")
    assert "alice" not in h and len(h) == 64
    assert hash_author("github", None) is None


def test_html_to_text():
    assert html_to_text("a &amp; b<p>c <b>d</b>") == "a & b\nc d"
    assert html_to_text(None) is None
