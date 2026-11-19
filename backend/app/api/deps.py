from __future__ import annotations

from urllib.parse import unquote

from fastapi import Header

DEFAULT_USER = "مختص تجريبي"


def current_user(x_user_name: str | None = Header(default=None)) -> str:
    """Demo identity: the UI sends the reviewer name in X-User-Name
    (URL-encoded). Replace with real authentication before deployment."""
    if not x_user_name:
        return DEFAULT_USER
    return unquote(x_user_name).strip()[:120] or DEFAULT_USER
