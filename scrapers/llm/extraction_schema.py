"""Strict validation of per-signal extraction JSON (stdlib only, no jsonschema dep).

The JSON schema is kept here as data (``EXTRACTION_SCHEMA``) for documentation and
mirrored by ``validate_extraction``, which is what the pipeline enforces.
"""

from __future__ import annotations

import json
import re
from typing import Any

ECONOMIC_INTENTS = ("High", "Medium", "Low", "Unspecified")
MAX_TEXT_CHARS = 1000
MAX_TAGS = 5
MAX_TAG_CHARS = 40

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["is_pain_point", "is_b2b", "problem_summary", "duct_tape",
                 "economic_intent", "persona", "workflow_tags"],
    "properties": {
        "is_pain_point": {"type": "boolean"},
        "is_b2b": {"type": "boolean"},
        "problem_summary": {"type": ["string", "null"], "maxLength": MAX_TEXT_CHARS},
        "duct_tape": {"type": ["string", "null"], "maxLength": MAX_TEXT_CHARS},
        "economic_intent": {"enum": list(ECONOMIC_INTENTS)},
        "persona": {"type": ["string", "null"], "maxLength": MAX_TEXT_CHARS},
        "workflow_tags": {"type": "array", "maxItems": MAX_TAGS,
                          "items": {"type": "string", "maxLength": MAX_TAG_CHARS}},
    },
}

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ExtractionValidationError(ValueError):
    pass


def parse_json(text: str) -> Any:
    """Parse model output; tolerates a single surrounding ```json fence only."""
    match = _FENCE_RE.match(text)
    try:
        return json.loads(match.group(1) if match else text)
    except json.JSONDecodeError as exc:
        raise ExtractionValidationError(f"not valid JSON: {exc.msg}") from exc


def _opt_text(data: dict, key: str) -> str | None:
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExtractionValidationError(f"{key} must be a string or null")
    value = value.strip()
    if len(value) > MAX_TEXT_CHARS:
        raise ExtractionValidationError(f"{key} longer than {MAX_TEXT_CHARS} chars")
    return value or None


def validate_extraction(data: Any) -> dict[str, Any]:
    """Return a normalised copy of ``data`` or raise ExtractionValidationError."""
    if not isinstance(data, dict):
        raise ExtractionValidationError("top level must be an object")
    required = set(EXTRACTION_SCHEMA["required"])
    missing = required - data.keys()
    extra = data.keys() - required
    if missing:
        raise ExtractionValidationError(f"missing keys: {sorted(missing)}")
    if extra:
        raise ExtractionValidationError(f"unexpected keys: {sorted(extra)}")
    for key in ("is_pain_point", "is_b2b"):
        if not isinstance(data[key], bool):
            raise ExtractionValidationError(f"{key} must be a boolean")
    if data["economic_intent"] not in ECONOMIC_INTENTS:
        raise ExtractionValidationError("economic_intent not in High/Medium/Low/Unspecified")
    tags = data["workflow_tags"]
    if not isinstance(tags, list) or len(tags) > MAX_TAGS:
        raise ExtractionValidationError(f"workflow_tags must be a list of <= {MAX_TAGS}")
    clean_tags: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or len(tag) > MAX_TAG_CHARS:
            raise ExtractionValidationError("workflow_tags items must be short strings")
        tag = tag.strip().lower()
        if tag and tag not in clean_tags:
            clean_tags.append(tag)
    out = {
        "is_pain_point": data["is_pain_point"],
        "is_b2b": data["is_b2b"],
        "problem_summary": _opt_text(data, "problem_summary"),
        "duct_tape": _opt_text(data, "duct_tape"),
        "economic_intent": data["economic_intent"],
        "persona": _opt_text(data, "persona"),
        "workflow_tags": clean_tags,
    }
    if out["is_pain_point"] and not out["problem_summary"]:
        raise ExtractionValidationError("pain point without problem_summary")
    if not out["is_pain_point"]:
        out["problem_summary"] = out["duct_tape"] = out["persona"] = None
    return out
