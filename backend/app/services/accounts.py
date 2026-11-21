"""Account and session handling on top of the database.

The rules themselves (hashing, roles, lockout) are in `auth.py`; this module
only reads and writes the `users` and `user_sessions` tables."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.models import User, UserSession
from app.services import auth


class InvalidLogin(Exception):
    """Unknown user, inactive account or wrong password. One message for all three,
    so the answer never reveals which usernames exist."""


class AccountLocked(Exception):
    def __init__(self, minutes: int):
        super().__init__(f"locked for {minutes} min")
        self.minutes = minutes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == auth.normalize_username(username)))


def create_user(
    db: Session, *, username: str, display_name: str, role: str, password: str, min_password_length: int = 10
) -> User:
    """Create an account. Raises ValueError (Arabic message) when something is invalid or taken."""
    uname = auth.validate_username(username)
    name = auth.validate_display_name(display_name)
    auth.validate_role(role)
    auth.validate_password(password, min_password_length)
    if _by_username(db, uname):
        raise ValueError("اسم المستخدم مستخدم من قبل.")
    # The display name goes into the audit log, so two accounts may not share one.
    if db.scalar(select(User).where(func.lower(User.display_name) == name.lower())):
        raise ValueError("الاسم الظاهر مستخدم من قبل. اختر اسمًا مختلفًا.")
    user = User(username=uname, display_name=name, role=role, password_hash=auth.hash_password(password))
    db.add(user)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def authenticate(
    db: Session, username: str, password: str, *, max_attempts: int = 5, lock_minutes: int = 15,
    now: datetime | None = None,
) -> User:
    now = now or _now()
    user = _by_username(db, username)
    if user is None or not user.is_active:
        auth.verify_password(password, auth.dummy_hash())  # keep timing similar
        raise InvalidLogin()
    if auth.is_locked(user.locked_until, now):
        raise AccountLocked(auth.minutes_left(user.locked_until, now))
    if not auth.verify_password(password, user.password_hash):
        user.failed_attempts, user.locked_until = auth.register_failure(
            user.failed_attempts, now, max_attempts=max_attempts, lock_minutes=lock_minutes
        )
        db.commit()
        if user.locked_until is not None:
            raise AccountLocked(auth.minutes_left(user.locked_until, now))
        raise InvalidLogin()
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    return user


def open_session(db: Session, user: User, hours: int, now: datetime | None = None) -> str:
    """Create a session and return the raw token (put it in the cookie; only its hash is stored)."""
    now = now or _now()
    db.execute(delete(UserSession).where(UserSession.expires_at < now))  # tidy up old ones
    token = auth.new_token()
    db.add(UserSession(token_hash=auth.hash_token(token), user_id=user.id, expires_at=now + timedelta(hours=hours)))
    db.commit()
    return token


def user_for_token(db: Session, token: str, now: datetime | None = None) -> User | None:
    now = now or _now()
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == auth.hash_token(token)))
    if sess is None or auth.as_utc(sess.expires_at) <= now:
        return None
    user = db.get(User, sess.user_id)
    return user if user is not None and user.is_active else None


def close_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == auth.hash_token(token)))
    db.commit()


def _close_all_sessions(db: Session, user: User) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))


def set_password(db: Session, username: str, password: str, min_password_length: int = 10) -> User:
    user = _by_username(db, username)
    if user is None:
        raise ValueError("لا يوجد حساب بهذا الاسم.")
    auth.validate_password(password, min_password_length)
    user.password_hash = auth.hash_password(password)
    user.failed_attempts, user.locked_until = 0, None
    _close_all_sessions(db, user)  # a new password signs the person out everywhere
    db.commit()
    return user


def set_active(db: Session, username: str, active: bool) -> User:
    user = _by_username(db, username)
    if user is None:
        raise ValueError("لا يوجد حساب بهذا الاسم.")
    user.is_active = active
    if not active:
        _close_all_sessions(db, user)
    db.commit()
    return user
