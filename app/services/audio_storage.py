from __future__ import annotations

from pathlib import Path
from uuid import uuid4


class AudioStorage:
    def __init__(self, media_root: Path) -> None:
        self.media_root = media_root
        self.media_root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, session_id: str, prefix: str, content: bytes, extension: str = "mp3") -> str:
        session_dir = self.media_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        safe_extension = extension.lstrip(".")
        filename = f"{prefix}_{uuid4().hex}.{safe_extension}"
        path = session_dir / filename
        path.write_bytes(content)
        return f"/media/{session_id}/{filename}"
