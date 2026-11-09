from __future__ import annotations

import os
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.api.routes.framework import router as framework_router
from backend.core import backtester

# Create a fresh app for testing this router in isolation
app = FastAPI()
app.include_router(framework_router)
client = TestClient(app)

def test_get_models():
    mock_models = {
        "alpha": [{"id": "momentum", "params": {}}],
        "portfolio_construction": [{"id": "equal", "params": {}}],
        "risk": [{"id": "max_drawdown", "params": {}}]
    }
    
    with patch("backend.api.routes.framework.list_models", return_value=mock_models):
        response = client.get("/api/framework/models")
        assert response.status_code == 200
        data = response.json()
        assert "alpha" in data
        assert "portfolio_construction" in data
        assert "risk" in data
        assert len(data["alpha"]) > 0

def test_run_backtest_happy_path(monkeypatch):
    # 1. Mock price data
    dates = pd.bdate_range(start="2023-01-01", periods=100)
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    df = pd.DataFrame(
        np.random.randn(100, 4).cumsum(axis=0) + 100,
        index=dates,
        columns=symbols
    )
    
    def mock_download(tickers, start, end):
        # Ensure we return a DataFrame with the requested tickers if they exist in our mock
        valid_tickers = [t for t in tickers if t in df.columns]
        if not valid_tickers and tickers:
             # Handle benchmark mock if needed, or just return empty if not found
             if tickers == ["^NSEI"]:
                 return pd.DataFrame({"^NSEI": np.random.randn(100).cumsum() + 100}, index=dates)
             return pd.DataFrame()
        return df[valid_tickers]

    monkeypatch.setattr(backtester, "_download_close", mock_download)
    
    # 2. Mock run_framework_backtest
    mock_result = {
        "summary": {"total_return": 0.1},
        "equity_curve": [1.0, 1.01, 1.1],
        "holdings": [],
        "insights": []
    }
    
    with patch("backend.api.routes.framework.run_framework_backtest", return_value=mock_result):
        payload = {
            "tickers": ["AAA", "BBB", "CCC", "DDD"],
            "benchmark": None,
            "alpha": {"id": "momentum", "params": {"lookback_days": 63}},
            "portfolio_construction": {"id": "equal", "params": {}},
            "risk": []
        }
        response = client.post("/api/framework/backtest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "equity_curve" in data
        assert "holdings" in data
        assert "insights" in data
        assert len(data["equity_curve"]) > 0

def test_run_backtest_empty_tickers():
    payload = {
        "tickers": [],
        "alpha": {"id": "momentum"},
        "portfolio_construction": {"id": "equal"}
    }
    # This should trigger Pydantic validation error
    response = client.post("/api/framework/backtest", json=payload)
    assert response.status_code == 422
