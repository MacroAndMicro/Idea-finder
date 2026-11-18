"""Normalized record shared by every source adapter (mirrors public.raw_signals)."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

SOURCE_PLATFORMS = frozenset(
    {"reddit", "github", "hackernews", "stackexchange", "g2", "capterra", "other"}
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\xa0]+")
# Line breaks and block-level boundaries become newlines so adjacent blocks
# (e.g. <li>a</li><li>b</li>) never fuse into one word.
_BLOCK_RE = re.compile(
    r"(?i)<\s*(?:br|/?(?:p|div|li|ul|ol|tr|pre|blockquote|table|h[1-6]))\b[^>]*>"
)


def hash_author(platform: str, handle: str | None) -> str | None:
    """One-way hash of an author handle; raw usernames are never stored."""
    if not handle:
        return None
    return hashlib.sha256(f"{platform}:{handle.strip().lower()}".encode()).hexdigest()


def content_hash(title: str | None, body: str | None) -> str:
    norm = " ".join(f"{title or ''} {body or ''}".lower().split())
    return hashlib.sha256(norm.encode()).hexdigest()


def html_to_text(value: str | None) -> str | None:
    """Convert API-provided HTML fragments to plain text (not page scraping)."""
    if value is None:
        return None
    text = _BLOCK_RE.sub("\n", value)
    text = html.unescape(_TAG_RE.sub("", text))
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line) or None


def from_unix(ts: int | float | None) -> datetime | None:
    return None if ts is None else datetime.fromtimestamp(ts, tz=UTC)


@dataclass(frozen=True, slots=True)
class RawSignal:
    source_platform: str
    external_id: str
    url: str
    title: str | None = None
    body: str | None = None
    author_handle_hash: str | None = None
    score: int | None = None
    comment_count: int | None = None
    tags: list[str] = field(default_factory=list)
    source_created_at: datetime | None = None
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.source_platform not in SOURCE_PLATFORMS:
            raise ValueError(f"unknown source_platform: {self.source_platform!r}")
        if not self.external_id or not self.url:
            raise ValueError("external_id and url are required")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self.title, self.body))

    def to_row(self) -> dict[str, Any]:
        """Dict ready for insert into public.raw_signals."""
        row = asdict(self)
        if self.source_created_at is not None:
            row["source_created_at"] = self.source_created_at.isoformat()
        return row
