from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.agent.tools.market_tools as mt
from backend.api.routes import research as research_routes
from backend.core.research import service as research_service


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(research_routes.router)
    return TestClient(app)


def test_search_endpoint_returns_query_and_results(monkeypatch):
    def fake_search(query: str, *, k: int = 10):
        return [{"title": "Factor Momentum", "score": 0.91, "query": query, "k": k}]

    monkeypatch.setattr(research_routes.service, "search", fake_search)

    response = _client().get("/api/research/search", params={"q": "momentum", "k": 3})

    assert response.status_code == 200
    assert response.json() == {
        "query": "momentum",
        "results": [{"title": "Factor Momentum", "score": 0.91, "query": "momentum", "k": 3}],
    }


def test_search_endpoint_rejects_blank_query():
    response = _client().get("/api/research/search", params={"q": "  "})

    assert response.status_code == 400
    assert response.json()["detail"] == "q is required"


def test_items_endpoint_clamps_limit(monkeypatch):
    captured = {}

    def fake_list_items(*, limit: int = 50):
        captured["limit"] = limit
        return [{"title": "Research Item"}]

    monkeypatch.setattr(research_routes.service, "list_items", fake_list_items)

    response = _client().get("/api/research/items", params={"limit": 500})

    assert response.status_code == 200
    assert captured["limit"] == 200
    assert response.json() == {"items": [{"title": "Research Item"}]}


@pytest.mark.asyncio
async def test_ingest_endpoint_uses_service(monkeypatch):
    captured = {}

    async def fake_ingest_arxiv(
        query: str = "cat:q-fin.*",
        *,
        max_results: int = 25,
        with_fulltext: bool = True,
    ):
        captured["query"] = query
        captured["max_results"] = max_results
        captured["with_fulltext"] = with_fulltext
        return {"ingested": 2, "fetched": 3, "query": query}

    monkeypatch.setattr(research_routes.service, "ingest_arxiv", fake_ingest_arxiv)

    response = _client().post(
        "/api/research/ingest",
        json={"query": "cat:q-fin.ST", "max_results": 7, "with_fulltext": False},
    )

    assert response.status_code == 200
    assert captured == {"query": "cat:q-fin.ST", "max_results": 7, "with_fulltext": False}
    assert response.json() == {"ingested": 2, "fetched": 3, "query": "cat:q-fin.ST"}


@pytest.mark.asyncio
async def test_ingest_url_endpoint_uses_service_and_rejects_blank_url(monkeypatch):
    service_payload = {
        "ingested": True,
        "url": "https://example.com/a",
        "title": "Example",
        "text_chars": 123,
    }

    async def fake_ingest_url(url: str):
        assert url == "https://example.com/a"
        return service_payload

    monkeypatch.setattr(research_routes.service, "ingest_url", fake_ingest_url)

    response = _client().post(
        "/api/research/ingest_url",
        json={"url": "https://example.com/a"},
    )
    blank_response = _client().post("/api/research/ingest_url", json={"url": "  "})

    assert response.status_code == 200
    assert response.json() == service_payload
    assert blank_response.status_code == 400
    assert blank_response.json()["detail"] == "url is required"


@pytest.mark.asyncio
async def test_search_research_tool_returns_trimmed_shape(monkeypatch):
    long_abstract = "a" * 650

    def fake_search(query: str, *, k: int = 10):
        return [{
            "id": "1",
            "source": "arxiv",
            "external_id": "1234.5678",
            "title": "Volatility Forecasting",
            "authors": ["A. Quant", "B. Research"],
            "abstract": long_abstract,
            "url": "https://arxiv.org/abs/1234.5678",
            "categories": ["q-fin.ST"],
            "published_at": "2026-01-01",
            "created_at": "2026-01-02",
            "score": 0.87,
        }]

    monkeypatch.setattr(research_service, "search", fake_search)

    out = await mt.search_research({"query": "vol forecasting", "k": 4})

    assert out["query"] == "vol forecasting"
    assert out["count"] == 1
    assert out["results"] == [{
        "title": "Volatility Forecasting",
        "authors": ["A. Quant", "B. Research"],
        "url": "https://arxiv.org/abs/1234.5678",
        "published_at": "2026-01-01",
        "score": 0.87,
        "abstract": "a" * 600,
    }]
    assert "note" not in out


@pytest.mark.asyncio
async def test_search_research_tool_returns_note_when_empty(monkeypatch):
    def fake_search(query: str, *, k: int = 10):
        return []

    monkeypatch.setattr(research_service, "search", fake_search)

    out = await mt.search_research({"query": "missing topic"})

    assert out["query"] == "missing topic"
    assert out["count"] == 0
    assert out["results"] == []
    assert out["note"] == "No indexed research yet — ingest via POST /api/research/ingest first."
