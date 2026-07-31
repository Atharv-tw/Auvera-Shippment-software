"""Minimal local file storage for uploaded workbooks."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings

settings = get_settings()


def save_upload(content: bytes, suffix: str = ".xlsx") -> str:
    d = Path(settings.upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return str(path)
