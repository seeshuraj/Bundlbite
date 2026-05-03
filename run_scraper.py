"""Windows-safe entrypoint for Bundlbite Scraper."""
import sys
import asyncio

# Set BEFORE any other import
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # reload=False on Windows — WatchFiles reloader spawns a child process
    # that resets the event loop policy, breaking Playwright subprocess launch.
    # For dev file-watching on Windows, restart manually after changes.
    is_windows = sys.platform == "win32"
    uvicorn.run(
        "scraper.main:app",
        host="0.0.0.0",
        port=8001,
        reload=not is_windows,  # False on Windows, True on Linux/Mac
        loop="asyncio",
    )
