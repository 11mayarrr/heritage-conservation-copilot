"""Accounts, passwords, roles and login-lockout rules.

Pure module (standard library only, no database): everything here can be unit
tested without the web stack. The database side lives in `accounts.py`.

Roles (decision of the team, step 9 of the plan):
  - assistant (مساعد): uploads photos and edits regions.
  - specialist (مختص): the only role that may APPROVE. This enforces the
    project principle "the agent proposes, the specialist decides".
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import math
import re
import secrets
from datetime import datetime, timedelta, timezone

ASSISTANT = "assistant"
SPECIALIST = "specialist"
ROLES = (ASSISTANT, SPECIALIST)
ROLE_AR = {ASSISTANT: "مساعد", SPECIALIST: "مختص"}

# Actions that need a role check. Anything not listed is denied (deny by default).
VIEW = "view"
EDIT = "edit"
APPROVE = "approve"
_PERMISSIONS: dict[str, frozenset[str]] = {
    VIEW: frozenset(ROLES),
    EDIT: frozenset(ROLES),
    APPROVE: frozenset({SPECIALIST}),
}

NOT_LOGGED_IN_AR = "سجّل الدخول أولًا، أو انتهت جلستك."
BAD_LOGIN_AR = "اسم المستخدم أو كلمة السر غير صحيحة."
APPROVE_FORBIDDEN_AR = "الاعتماد للمختص فقط. حسابك بدور «مساعد»."


def can(role: str | None, action: str) -> bool:
    return role in _PERMISSIONS.get(action, frozenset())


# ---- passwords -------------------------------------------------------------

# scrypt (memory-hard, in the standard library). ~50 ms per check on a laptop.
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
_MAXMEM = 64 * 1024 * 1024
MAX_PASSWORD_LEN = 128


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=_MAXMEM)


def hash_password(password: str) -> str:
    """Return 'scrypt$N$r$p$salt$hash'. A fresh random salt per password."""
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _N, _R, _P, _DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        got = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


_dummy: str | None = None


def dummy_hash() -> str:
    """A valid hash nobody knows the password of. Checking against it for an unknown
    username keeps the response time similar, so timing does not reveal which
    usernames exist."""
    global _dummy
    if _dummy is None:
        _dummy = hash_password(secrets.token_urlsafe(16))
    return _dummy


# ---- session tokens --------------------------------------------------------


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only this hash is stored, so a copy of the database cannot be used to log in."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---- validation (messages are shown to the person creating the account) ----

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_username(username: str) -> str:
    u = normalize_username(username)
    if not _USERNAME_RE.match(u):
        raise ValueError("اسم المستخدم من 3 إلى 32 حرفًا إنجليزيًا صغيرًا أو أرقامًا أو (. _ -) ويبدأ بحرف أو رقم.")
    return u


def validate_display_name(name: str) -> str:
    n = " ".join((name or "").split())
    if not 2 <= len(n) <= 120 or any(ord(c) < 32 for c in n):
        raise ValueError("الاسم الظاهر من حرفين إلى 120 حرفًا.")
    return n


def validate_role(role: str) -> str:
    if role not in ROLES:
        raise ValueError("الدور يجب أن يكون assistant (مساعد) أو specialist (مختص).")
    return role


def validate_password(password: str, min_len: int = 10) -> str:
    if len(password or "") < min_len:
        raise ValueError(f"كلمة السر قصيرة: {min_len} أحرف على الأقل.")
    if len(password) > MAX_PASSWORD_LEN:
        raise ValueError(f"كلمة السر طويلة: {MAX_PASSWORD_LEN} حرفًا على الأكثر.")
    if password.strip() != password:
        raise ValueError("كلمة السر لا تبدأ ولا تنتهي بمسافة.")
    return password


# ---- lockout after repeated failures --------------------------------------


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; this repo stores UTC, so treat naive as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def is_locked(locked_until: datetime | None, now: datetime) -> bool:
    lu = as_utc(locked_until)
    return lu is not None and lu > now


def minutes_left(locked_until: datetime | None, now: datetime) -> int:
    lu = as_utc(locked_until)
    if lu is None or lu <= now:
        return 0
    return math.ceil((lu - now).total_seconds() / 60)


def register_failure(
    failed: int, now: datetime, *, max_attempts: int, lock_minutes: int
) -> tuple[int, datetime | None]:
    """Count one failed login. Returns (new counter, locked_until or None).
    After `max_attempts` failures the account is locked and the counter restarts."""
    failed += 1
    if failed >= max_attempts:
        return 0, now + timedelta(minutes=lock_minutes)
    return failed, None
