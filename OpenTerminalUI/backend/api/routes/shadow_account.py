from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.auth.deps import get_current_user
from backend.models import JournalEntry, User
from backend.shadow_account.schemas import ShadowReportRequest
from backend.shadow_account.service import build_report, trade_from_journal

router = APIRouter(prefix="/api/shadow-account", tags=["shadow-account"])


@router.get("/report")
def get_shadow_account_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Build a shadow-account report from the authenticated user's journal."""

    rows = db.query(JournalEntry).filter(JournalEntry.user_id == str(current_user.id)).all()
    trades = [trade_from_journal(row) for row in rows]
    return build_report(trades)


@router.post("/report")
def post_shadow_account_report(
    payload: ShadowReportRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """Build a shadow-account report from an ad-hoc canonical trade list."""

    return build_report(payload.trades, min_samples=payload.min_samples)
