from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    scope: str = Field(default="workspace", max_length=80)
    page: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    scope: str | None = Field(default=None, max_length=80)
    page: str | None = Field(default=None, min_length=1, max_length=240)
    payload: dict[str, Any] | None = None
    description: str | None = None


class SavedViewOut(BaseModel):
    id: str
    user_id: str
    name: str
    scope: str
    page: str
    payload: dict[str, Any]
    description: str = ""
    created_at: datetime
    updated_at: datetime
