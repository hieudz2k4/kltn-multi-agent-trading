from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchAutopilotHypothesis(Base):
    """Persisted research hypothesis specification and latest verdict."""

    __tablename__ = "research_autopilot_hypotheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    spec_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    verdict_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ResearchAutopilotRun(Base):
    """Persisted research autopilot run result."""

    __tablename__ = "research_autopilot_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("research_autopilot_hypotheses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

