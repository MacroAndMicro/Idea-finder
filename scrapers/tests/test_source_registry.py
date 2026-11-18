"""IF-56: every place that lists ingestion sources must agree on the same source keys.

Adding a source to one collection but not the others would silently skip it or crash the
pipeline, so this guard fails fast instead.
"""

from __future__ import annotations

import pytest

from scrapers import ingest, pipeline
from scrapers.models import SOURCE_PLATFORMS

COLLECTIONS = {
    "ingest.ADAPTERS": set(ingest.ADAPTERS),
    "ingest.DEFAULT_QUERIES": set(ingest.DEFAULT_QUERIES),
    "pipeline.DEFAULT_SOURCES": set(pipeline.DEFAULT_SOURCES),
    "pipeline.SOURCE_SECRETS": set(pipeline.SOURCE_SECRETS),
}


@pytest.mark.parametrize("name", sorted(COLLECTIONS))
def test_collection_matches_adapter_registry(name: str) -> None:
    keys = COLLECTIONS[name]
    expected = COLLECTIONS["ingest.ADAPTERS"]
    assert keys == expected, (
        f"{name} differs from ingest.ADAPTERS: "
        f"extra {sorted(keys - expected)}, missing {sorted(expected - keys)}"
    )


@pytest.mark.parametrize("name", sorted(COLLECTIONS))
def test_every_source_is_a_raw_signal_platform(name: str) -> None:
    unknown = COLLECTIONS[name] - SOURCE_PLATFORMS
    assert not unknown, f"{name} has keys that RawSignal rejects: {sorted(unknown)}"


def test_default_sources_has_no_duplicates() -> None:
    assert len(pipeline.DEFAULT_SOURCES) == len(set(pipeline.DEFAULT_SOURCES))


def test_ingest_required_keys_are_declared_in_pipeline_secrets() -> None:
    # ingest.REQUIRED_KEY is the subset of sources with a single mandatory secret; the
    # pipeline preflight must check that same variable or it would start a doomed stage.
    for source, var in ingest.REQUIRED_KEY.items():
        assert source in pipeline.SOURCE_SECRETS, source
        assert var in pipeline.SOURCE_SECRETS[source], (source, var)
