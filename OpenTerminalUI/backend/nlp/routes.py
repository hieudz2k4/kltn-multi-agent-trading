from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.nlp.filing_parser import get_conviction_record, ingest_symbol_filings

router = APIRouter(prefix="/stock-picking/conviction", tags=["stock-conviction"])


class FilingDocument(BaseModel):
    title: str = ""
    text: str = ""
    summary: str = ""
    published_at: str | None = None
    source: str = ""
    url: str = ""


class ConvictionIngestRequest(BaseModel):
    symbol: str
    market: str | None = None
    record_date: str | None = None
    use_llm: bool = True
    documents: list[FilingDocument] = Field(default_factory=list)


@router.get("/{symbol}")
def get_symbol_conviction(
    symbol: str,
    market: str | None = Query(default=None),
    record_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_conviction_record(db, symbol=symbol, market=market, record_date=record_date)
    if row is None:
        raise HTTPException(status_code=404, detail="No conviction record available for symbol")
    return row


@router.post("/ingest")
async def post_ingest_conviction(payload: ConvictionIngestRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await ingest_symbol_filings(
        db,
        symbol=payload.symbol,
        market=payload.market,
        documents=[doc.model_dump() for doc in payload.documents],
        record_date=payload.record_date,
        use_llm=payload.use_llm,
    )

