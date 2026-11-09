from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from backend.api.routes import scripting
from backend.core.models import PythonExecuteRequest
from backend.core.strategy_runner import StrategyRunner


# Canonical CPython sandbox-escape building block: dunder traversal from any
# literal reaches every loaded class (e.g. subprocess.Popen) without using
# `import` or any restricted builtin name. Blocking imports + restricting
# __builtins__ is NOT sufficient; attribute traversal must be rejected too.
_ESCAPE_EXPR = "().__class__.__base__.__subclasses__()"


def test_execute_python_blocks_dunder_traversal() -> None:
    payload = PythonExecuteRequest(code=f"result = {_ESCAPE_EXPR}", timeout_seconds=2)
    try:
        asyncio.run(scripting.execute_python(payload))
    except Exception as exc:  # FastAPI HTTPException
        assert "blocked" in str(getattr(exc, "detail", exc)).lower()
    else:
        raise AssertionError("Expected dunder attribute access to be blocked")


def test_execute_python_blocks_subscript_dunder_globals() -> None:
    code = "def f():\n    pass\nresult = f.__globals__"
    payload = PythonExecuteRequest(code=code, timeout_seconds=2)
    try:
        asyncio.run(scripting.execute_python(payload))
    except Exception as exc:
        assert "blocked" in str(getattr(exc, "detail", exc)).lower()
    else:
        raise AssertionError("Expected __globals__ access to be blocked")


def test_inline_strategy_blocks_dunder_traversal() -> None:
    frame = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [1.0, 2.0, 3.0],
            "low": [1.0, 2.0, 3.0],
            "close": [1.0, 2.0, 3.0],
            "volume": [10, 20, 30],
        }
    )
    strategy = (
        "def generate_signals(df, context):\n"
        f"    _ = {_ESCAPE_EXPR}\n"
        "    return [0] * len(df)\n"
    )
    with pytest.raises(ValueError) as excinfo:
        StrategyRunner(timeout_seconds=2.0).run(strategy, frame)
    assert "attribute" in str(excinfo.value).lower() or "blocked" in str(excinfo.value).lower()
