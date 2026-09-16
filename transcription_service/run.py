"""Entrypoint alternativo para rodar via `python run.py` (dev local)."""

import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
