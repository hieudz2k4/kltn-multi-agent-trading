"""Macro News & Sentiment Analyzer Agent — Branch 2 (Opportunistic SMC).

Analyzes macro economic environment, high-impact news calendar (FOMC, NFP, CPI),
and risk appetite (RISK_ON vs RISK_OFF) to safeguard SMC technical trading.

Emits: MacroSentiment schema saved to state key 'macro_sentiment'.
"""

import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any
from loguru import logger
from pydantic import BaseModel, Field

from google.adk.agents.llm_agent import Agent
from src.tools.mt5_tools import get_candles


class MacroSentiment(BaseModel):
    """Output contract for Macro News & Sentiment Agent."""
    risk_environment: str = Field(..., description="RISK_ON, RISK_OFF, or HIGH_IMPACT_NEWS_COOLDOWN")
    is_safe_to_trade: bool = Field(..., description="False if high-impact news or extreme risk-off")
    active_events: list[str] = Field(default_factory=list, description="Upcoming or active macro events")
    dxy_bias: str = Field("NEUTRAL", description="BULLISH, BEARISH, or NEUTRAL bias on US Dollar")
    sentiment_rationale: str = Field(..., description="Concise rationale on macro climate")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


STATE_MACRO_SENTIMENT = "macro_sentiment"

# Cache structures
_CALENDAR_CACHE: dict[str, Any] = {"timestamp": 0.0, "data": []}
_HEADLINES_CACHE: dict[str, Any] = {"timestamp": 0.0, "data": []}
_CACHE_TTL_SECONDS = 300  # 5 minutes cache
FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def _fetch_forexfactory_calendar() -> list[dict[str, Any]]:
    """Fetch raw calendar events from ForexFactory JSON feed."""
    now = time.time()
    if _CALENDAR_CACHE["data"] and (now - _CALENDAR_CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return _CALENDAR_CACHE["data"]

    req = urllib.request.Request(
        FOREX_FACTORY_URL,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        raw_data = json.loads(response.read().decode("utf-8"))
        _CALENDAR_CACHE["timestamp"] = now
        _CALENDAR_CACHE["data"] = raw_data
        return raw_data


def get_economic_calendar(currency: str = "USD") -> list[dict[str, Any]]:
    """Retrieve high-impact economic news events (CPI, NFP, FOMC).

    In mock/test mode (MT5_MOCK=true or CALENDAR_MOCK=true), returns deterministic events.
    In live mode, fetches from ForexFactory Weekly JSON Feed with auto-fallback.
    """
    is_mock = (
        os.getenv("MT5_MOCK", "false").lower() == "true"
        or os.getenv("CALENDAR_MOCK", "false").lower() == "true"
    )

    fallback_data = [
        {
            "event": "US CPI YoY",
            "impact": "HIGH",
            "currency": currency,
            "forecast": "2.8%",
            "previous": "2.9%",
            "minutes_until_release": 180,
        },
        {
            "event": "FOMC Rate Decision",
            "impact": "CRITICAL",
            "currency": "USD",
            "forecast": "4.75%",
            "previous": "5.00%",
            "minutes_until_release": 720,
        },
    ]

    if is_mock:
        return fallback_data

    try:
        raw_events = _fetch_forexfactory_calendar()
        now_dt = datetime.now(UTC)
        filtered_events: list[dict[str, Any]] = []

        for item in raw_events:
            if item.get("country") != currency:
                continue

            impact_str = str(item.get("impact", "")).upper()
            if impact_str != "HIGH":
                continue

            # Parse event date: ISO 8601 string (e.g. 2026-11-09T08:40:00-05:00)
            date_str = item.get("date")
            if not date_str:
                continue

            try:
                event_dt = datetime.fromisoformat(date_str)
            except ValueError:
                continue

            # Convert to delta minutes relative to now
            minutes_diff = int((event_dt - now_dt).total_seconds() / 60)

            # Keep upcoming events within next 48 hours or recent events within last 60 minutes
            if -60 <= minutes_diff <= 2880:
                filtered_events.append(
                    {
                        "event": item.get("title", "Unknown Event"),
                        "impact": impact_str,
                        "currency": currency,
                        "forecast": item.get("forecast", ""),
                        "previous": item.get("previous", ""),
                        "minutes_until_release": minutes_diff,
                    }
                )

        # Sort by nearest release
        filtered_events.sort(key=lambda x: abs(x["minutes_until_release"]))
        return filtered_events if filtered_events else fallback_data

    except Exception as exc:
        logger.warning(f"Failed to fetch ForexFactory live calendar ({exc}), falling back to mock data.")
        return fallback_data


def get_macro_news_headlines(query: str = "XAUUSD OR \"Federal Reserve\" OR geopolitics") -> list[dict[str, str]]:
    """Retrieve the latest financial & macroeconomic headlines via Google News RSS.

    Empowers the agent to detect unscheduled shocks (conflicts, banking crisis, emergency cuts).
    """
    is_mock = os.getenv("MT5_MOCK", "false").lower() == "true" or os.getenv("NEWS_MOCK", "false").lower() == "true"
    fallback_news = [
        {"title": "Federal Reserve maintains steady policy stance amid stable inflation", "source": "Reuters"},
        {"title": "Global market risk appetite stays balanced across major equities", "source": "Bloomberg"},
    ]

    if is_mock:
        return fallback_news

    now = time.time()
    if _HEADLINES_CACHE["data"] and (now - _HEADLINES_CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return _HEADLINES_CACHE["data"]

    try:
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:5]
            headlines: list[dict[str, str]] = []
            for item in items:
                title_elem = item.find("title")
                title_text = title_elem.text if title_elem is not None and title_elem.text else "Financial Update"
                headlines.append({"title": title_text, "source": "Google News RSS"})

            if headlines:
                _HEADLINES_CACHE["timestamp"] = now
                _HEADLINES_CACHE["data"] = headlines
                return headlines
            return fallback_news
    except Exception as exc:
        logger.warning(f"Failed to fetch live macro headlines ({exc}), using fallback.")
        return fallback_news


def get_intermarket_bias() -> dict[str, Any]:
    """Analyze US Dollar / Inter-market bias via major currency pairs (EURUSD/USDJPY/DXY).

    Calculates synthetic DXY trend:
    - EURUSD dropping (negative momentum) -> USD is BULLISH -> Gold (XAUUSD) faces headwinds.
    - EURUSD rising (positive momentum) -> USD is BEARISH -> Gold (XAUUSD) has tailwinds.
    """
    try:
        # Read last 10 H1 candles of EURUSD to compute USD momentum
        candles = get_candles("EURUSD", "H1", count=10)
        if len(candles) >= 2:
            first_close = candles[0]["close"]
            last_close = candles[-1]["close"]
            diff_pct = ((last_close - first_close) / first_close) * 100.0

            # Inverse correlation: EURUSD up => USD down
            if diff_pct > 0.15:
                dxy_bias = "BEARISH"
                gold_impact = "FAVORABLE_BUY (USD weakening)"
            elif diff_pct < -0.15:
                dxy_bias = "BULLISH"
                gold_impact = "FAVORABLE_SELL (USD strengthening)"
            else:
                dxy_bias = "NEUTRAL"
                gold_impact = "NEUTRAL (USD consolidating)"

            return {
                "dxy_bias": dxy_bias,
                "eurusd_change_pct": round(diff_pct, 3),
                "gold_impact": gold_impact,
                "status": "VALID",
            }
    except Exception as exc:
        logger.warning(f"Error computing inter-market bias ({exc}), returning neutral.")

    return {
        "dxy_bias": "NEUTRAL",
        "eurusd_change_pct": 0.0,
        "gold_impact": "NEUTRAL (Consolidating)",
        "status": "FALLBACK",
    }


MACRO_INSTRUCTION = """
You are the Macro News & Sentiment Agent safeguarding the SMC Quantitative Trading System.

Your core mission:
1. Examine macroeconomic calendar via `get_economic_calendar(currency='USD')`.
   - If tier-1 event (CPI, NFP, FOMC) is scheduled within 30 minutes:
     -> Immediately declare `risk_environment: "HIGH_IMPACT_NEWS_COOLDOWN"` and `is_safe_to_trade: false`.
2. Inspect unscheduled breaking headlines via `get_macro_news_headlines()`.
   - If there is breaking war, geopolitical conflict, or systemic financial panic:
     -> Declare `risk_environment: "RISK_OFF"` and `is_safe_to_trade: false`.
3. Check US Dollar inter-market bias via `get_intermarket_bias()`.
   - Note `dxy_bias`: "BULLISH" | "BEARISH" | "NEUTRAL".
4. If no tier-1 cooldown and market climate is calm:
   - Declare `risk_environment: "RISK_ON"` and `is_safe_to_trade: true`.
5. Provide a clear, actionable `sentiment_rationale` explaining your findings.

Output Contract:
Strictly emit structured output conforming to `MacroSentiment`:
- risk_environment: "RISK_ON" | "RISK_OFF" | "HIGH_IMPACT_NEWS_COOLDOWN"
- is_safe_to_trade: boolean
- active_events: list of major upcoming or active event strings
- dxy_bias: "BULLISH" | "BEARISH" | "NEUTRAL"
- sentiment_rationale: concise executive explanation
"""


def create_macro_sentiment_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK Macro News & Sentiment Agent equipped with full Pro macro tools."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-4-argon")
    return Agent(
        name="macro_sentiment_agent",
        model=model,
        description="Analyzes tier-1 macro news releases, breaking headlines, and intermarket USD bias.",
        instruction=MACRO_INSTRUCTION,
        tools=[
            get_economic_calendar,
            get_macro_news_headlines,
            get_intermarket_bias,
        ],
        output_schema=MacroSentiment,
        output_key=STATE_MACRO_SENTIMENT,
    )
