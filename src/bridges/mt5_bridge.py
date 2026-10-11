"""MT5 Bridge — RPyC client connecting to MetaTrader 5 Docker container.

Production: rpyc.connect("127.0.0.1", 8001)
"""

import os
from contextlib import contextmanager

import rpyc
from loguru import logger

_MT5_HOST = os.getenv("MT5_HOST", "127.0.0.1")
_MT5_PORT = int(os.getenv("MT5_PORT", "8001"))


class MT5BridgeConnectionError(ConnectionError):
    """Raised when RPyC connection to MT5 Docker fails."""


@contextmanager
def get_mt5_connection():
    """Context manager yielding an RPyC connection to MT5 bridge."""
    conn = None
    try:
        conn = rpyc.connect(
            _MT5_HOST,
            _MT5_PORT,
            config={"sync_request_timeout": 30},
        )
        yield conn.root
    except (OSError, ConnectionRefusedError, TimeoutError) as exc:
        logger.error(f"MT5 RPyC connection failed at {_MT5_HOST}:{_MT5_PORT}: {exc}")
        raise MT5BridgeConnectionError(f"Cannot connect to MT5 Docker at {_MT5_HOST}:{_MT5_PORT}") from exc
    finally:
        if conn:
            conn.close()
