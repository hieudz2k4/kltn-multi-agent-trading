"""TradingView CDP Bridge — connects to TradingView Desktop via Chrome DevTools Protocol.

Production: TradingView Desktop running with --remote-debugging-port=9222
CDP endpoint: http://127.0.0.1:9222/json
"""

import json
import os
from typing import Any

import httpx
from loguru import logger

_TV_CDP_HOST = os.getenv("TV_CDP_HOST", "127.0.0.1")
_TV_CDP_PORT = int(os.getenv("TV_CDP_PORT", "9222"))
_TV_CDP_URL = f"http://{_TV_CDP_HOST}:{_TV_CDP_PORT}"


class CDPConnectionError(ConnectionError):
    """Raised when communication with Chrome DevTools Protocol fails."""


def _get_active_page_ws_url() -> str | None:
    """Discover the active TradingView chart tab WebSocket debug URL."""
    try:
        response = httpx.get(f"{_TV_CDP_URL}/json", timeout=5.0)
        response.raise_for_status()
        pages = response.json()
        for page in pages:
            if "tradingview" in page.get("url", "").lower() and page.get("webSocketDebuggerUrl"):
                return page["webSocketDebuggerUrl"]
        return None
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.error(f"Cannot reach TradingView CDP at {_TV_CDP_URL}: {exc}")
        raise CDPConnectionError(f"TradingView CDP endpoint unreachable at {_TV_CDP_URL}") from exc


async def _evaluate_js(expression: str) -> Any:
    """Execute JavaScript in TradingView tab and return the result."""
    import websockets

    ws_url = _get_active_page_ws_url()
    if not ws_url:
        raise CDPConnectionError("TradingView active chart tab WebSocket debugger URL not found")

    async with websockets.connect(ws_url) as ws:
        payload = json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True},
        })
        await ws.send(payload)
        response = json.loads(await ws.recv())
        return response.get("result", {}).get("result", {}).get("value")
