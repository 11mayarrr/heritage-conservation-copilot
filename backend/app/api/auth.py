"""Login, logout and "who am I". The session lives in an HttpOnly cookie."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, current_account
from app.config import get_settings
from app.database.models import User
from app.database.session import get_db
from app.services import accounts, auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class Me(BaseModel):
    username: str
    display_name: str
    role: str
    role_ar: str


def _me(u: User) -> Me:
    return Me(username=u.username, display_name=u.display_name, role=u.role, role_ar=auth.ROLE_AR.get(u.role, u.role))


@router.post("/login", response_model=Me)
def login(body: LoginBody, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    try:
        user = accounts.authenticate(
            db, body.username, body.password, max_attempts=s.login_max_attempts, lock_minutes=s.login_lock_minutes
        )
    except accounts.AccountLocked as e:
        raise HTTPException(
            status_code=429,
            detail=f"أُوقف الدخول مؤقتًا بعد محاولات فاشلة. حاول بعد {e.minutes} دقيقة.",
        )
    except accounts.InvalidLogin:
        raise HTTPException(status_code=401, detail=auth.BAD_LOGIN_AR)
    token = accounts.open_session(db, user, s.session_hours)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=s.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        path="/",
    )
    return _me(user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        accounts.close_session(db, token)
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/me", response_model=Me)
def me(account: User = Depends(current_account)):
    return _me(account)
