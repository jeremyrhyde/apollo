"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the UI — so the same build
works standalone (http://pi:8001/) and behind Pantheon's gateway
(http://pi:8000/apollo/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

from config import Settings


def test_default_port_is_8001(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert Settings(_env_file=None).PORT == 8001
