from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.research import service

router = APIRouter(prefix="/api/research", tags=["research"])


class IngestRequest(BaseModel):
    query: str = "cat:q-fin.*"
    max_results: int = Field(25, ge=1, le=100)
    with_fulltext: bool = True


@router.post("/ingest")
async def ingest(payload: IngestRequest) -> dict[str, Any]:
    return await service.ingest_arxiv(
        payload.query,
        max_results=payload.max_results,
        with_fulltext=payload.with_fulltext,
    )


class IngestUrlRequest(BaseModel):
    url: str


@router.post("/ingest_url")
async def ingest_url(payload: IngestUrlRequest) -> dict[str, Any]:
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    return await service.ingest_url(url)


@router.get("/search")
async def search(q: str, k: int = 10) -> dict[str, Any]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    k = max(1, min(50, k))
    return {"query": q, "results": service.search(q, k=k)}


@router.get("/items")
async def items(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(200, limit))
    return {"items": service.list_items(limit=limit)}
