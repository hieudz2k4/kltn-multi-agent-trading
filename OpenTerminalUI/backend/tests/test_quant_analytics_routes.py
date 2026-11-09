from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.fixed_income import router as fixed_income_router
from backend.api.routes.options import router as options_router

app = FastAPI()
app.include_router(fixed_income_router)
app.include_router(options_router)

client = TestClient(app)

def test_bond_analytics_success():
    payload = {
        "coupon_rate": 0.05,
        "years_to_maturity": 10,
        "frequency": 2,
        "ytm": 0.05
    }
    response = client.post("/api/fixed-income/bond-analytics", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert abs(data["price"] - 100.0) < 1e-2
    assert "modified_duration" in data
    assert "convexity" in data
    assert "dv01" in data

def test_bond_analytics_validation_error():
    # Both ytm and price provided
    payload = {
        "coupon_rate": 0.05,
        "years_to_maturity": 10,
        "frequency": 2,
        "ytm": 0.05,
        "price": 100.0
    }
    response = client.post("/api/fixed-income/bond-analytics", json=payload)
    assert response.status_code == 422
    assert "Provide exactly one of ytm or price" in response.json()["detail"]

def test_option_greeks_success():
    payload = {
        "spot": 100,
        "strike": 100,
        "time_to_expiry": 1,
        "rate": 0.05,
        "volatility": 0.2
    }
    response = client.post("/api/options/greeks", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0 < data["delta"] < 1
    assert data["gamma"] > 0

def test_option_implied_vol_success():
    payload = {
        "spot": 100,
        "strike": 100,
        "time_to_expiry": 1,
        "rate": 0.05,
        "market_price": 10.45,
        "option_type": "call"
    }
    response = client.post("/api/options/implied-vol", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert abs(data["implied_volatility"] - 0.2) < 1e-2
