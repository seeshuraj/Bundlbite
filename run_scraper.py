"""Windows-safe entrypoint for Bundlbite Scraper.
Sets WindowsSelectorEventLoopPolicy BEFORE uvicorn initialises,
so Playwright's asyncio.create_subprocess_exec works on Windows.
"""
import sys
import asyncio

# Must be before ANY uvicorn/fastapi import
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "scraper.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        loop="asyncio",
    )
