"""Who is making the request. Identity comes from the login session cookie, never
from anything the client types, so names in the audit log and reports can be trusted."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.models import User
from app.database.session import get_db
from app.services import accounts, auth

SESSION_COOKIE = "hcc_session"


def current_account(request: Request, db: Session = Depends(get_db)) -> User:
    """The signed-in account, or 401. Applied to every route except login."""
    token = request.cookies.get(SESSION_COOKIE)
    user = accounts.user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail=auth.NOT_LOGGED_IN_AR)
    return user


def current_user(account: User = Depends(current_account)) -> str:
    """Display name of the signed-in account (what the audit log records)."""
    return account.display_name


def require_specialist(account: User = Depends(current_account)) -> str:
    """For approval actions: only a specialist (مختص) may decide."""
    if not auth.can(account.role, auth.APPROVE):
        raise HTTPException(status_code=403, detail=auth.APPROVE_FORBIDDEN_AR)
    return account.display_name
