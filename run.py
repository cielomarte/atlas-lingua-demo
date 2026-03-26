from __future__ import annotations

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:create_app", factory=True, host=settings.host, port=settings.port, reload=settings.debug)
