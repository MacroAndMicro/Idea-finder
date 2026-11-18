"""Strict validation of the card-synthesis JSON (stdlib only, mirrors extraction_schema)."""

from __future__ import annotations

from typing import Any

from scrapers.llm.extraction_schema import ExtractionValidationError

MAX_TITLE_CHARS = 120
MAX_TEXT_CHARS = 1200
TEXT_KEYS = ("title", "problem_statement", "trigger_when", "market_size",
             "duct_tape_solutions", "mvp_wedge")

CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["valid_opportunity", *TEXT_KEYS],
    "properties": {
        "valid_opportunity": {"type": "boolean"},
        "title": {"type": "string", "minLength": 1, "maxLength": MAX_TITLE_CHARS},
        **{k: {"type": "string", "minLength": 1, "maxLength": MAX_TEXT_CHARS}
           for k in TEXT_KEYS if k != "title"},
    },
}


class CardValidationError(ExtractionValidationError):
    pass


def validate_card(data: Any) -> dict[str, Any]:
    """Return a normalised copy of ``data`` or raise CardValidationError."""
    if not isinstance(data, dict):
        raise CardValidationError("top level must be an object")
    required = set(CARD_SCHEMA["required"])
    missing, extra = required - data.keys(), data.keys() - required
    if missing:
        raise CardValidationError(f"missing keys: {sorted(missing)}")
    if extra:
        raise CardValidationError(f"unexpected keys: {sorted(extra)}")
    if not isinstance(data["valid_opportunity"], bool):
        raise CardValidationError("valid_opportunity must be a boolean")
    out: dict[str, Any] = {"valid_opportunity": data["valid_opportunity"]}
    for key in TEXT_KEYS:
        value = data[key]
        if not isinstance(value, str):
            raise CardValidationError(f"{key} must be a string")
        value = " ".join(value.split())
        limit = MAX_TITLE_CHARS if key == "title" else MAX_TEXT_CHARS
        if len(value) > limit:
            raise CardValidationError(f"{key} longer than {limit} chars")
        if not value and out["valid_opportunity"]:
            raise CardValidationError(f"{key} must not be empty")
        out[key] = value or "Unspecified"
    return out
