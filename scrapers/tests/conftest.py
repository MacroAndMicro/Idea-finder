from __future__ import annotations

import pytest

from scrapers.http_client import HttpClient
from scrapers.tests.helpers import FakeClock, FakeTransport


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_client(clock):
    def _make(responses, **kwargs) -> tuple[HttpClient, FakeTransport]:
        transport = FakeTransport(responses)
        client = HttpClient(transport=transport, sleep=clock.sleep, clock=clock.time, **kwargs)
        return client, transport

    return _make


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    def _blocked(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
