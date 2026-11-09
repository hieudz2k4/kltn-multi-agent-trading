import asyncio

from backend.mcp.server import run_stdio


if __name__ == "__main__":
    asyncio.run(run_stdio())
