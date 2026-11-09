from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal

from pydantic import ValidationError

from backend.strategy_export.mql5 import to_mql5
from backend.strategy_export.pine import to_pine
from backend.strategy_export.presets import PRESETS
from backend.strategy_export.spec import StrategySpec


def list_presets() -> dict[str, list[dict[str, Any]]]:
    """Return available strategy export presets."""
    return {"presets": [deepcopy(preset) for preset in PRESETS.values()]}


def generate(spec_dict: dict[str, Any], fmt: str) -> dict[str, Any]:
    """Validate a spec and generate code in the requested export format."""
    if fmt not in {"pine", "mql5"}:
        raise ValueError("format must be one of: pine, mql5")
    try:
        spec = StrategySpec(**spec_dict)
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"invalid strategy spec: {exc}") from exc

    language: Literal["pine", "mql5"] = "pine" if fmt == "pine" else "mql5"
    if language == "pine":
        code, warnings = to_pine(spec)
        extension = "pine"
    else:
        code, warnings = to_mql5(spec)
        extension = "mq5"
    return {
        "code": code,
        "language": language,
        "filename": f"{_slug(spec.name)}.{extension}",
        "warnings": warnings,
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "strategy"
