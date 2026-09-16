"""Windows-friendly launcher.

Playwright needs asyncio subprocess support, which on Windows requires the
Proactor event loop policy. Uvicorn's default setup resets the policy to
Selector, which breaks Playwright. Here we set Proactor first and then ask
uvicorn to skip its own loop setup via `loop="none"`.

On Linux/macOS this is equivalent to running `uvicorn main:app ...` directly.
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        loop="none",  # keep the Proactor policy we set above
        reload=False,
    )
