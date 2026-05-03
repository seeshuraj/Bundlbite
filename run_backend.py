"""Windows-safe entrypoint for Bundlbite Backend."""
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    is_windows = sys.platform == "win32"
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not is_windows,
        loop="asyncio",
    )
