"""Pure tests for accounts: passwords, tokens, roles, lockout, validation (no web stack needed)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import auth

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def test_password_hash_roundtrip_and_salt():
    h1, h2 = auth.hash_password("correct horse battery"), auth.hash_password("correct horse battery")
    assert h1 != h2  # fresh salt each time
    assert "correct horse" not in h1
    assert auth.verify_password("correct horse battery", h1)
    assert not auth.verify_password("correct horse batterY", h1)
    assert not auth.verify_password("", h1)


def test_arabic_password_works():
    h = auth.hash_password("كلمة-سر-طويلة-123")
    assert auth.verify_password("كلمة-سر-طويلة-123", h)
    assert not auth.verify_password("كلمة-سر-طويلة-124", h)


@pytest.mark.parametrize("bad", ["", "plain", "scrypt$x", "md5$1$2$3$4$5", "scrypt$16384$8$1$!!$!!"])
def test_garbage_stored_hash_is_rejected_not_crashing(bad):
    assert auth.verify_password("anything", bad) is False


def test_dummy_hash_is_valid_but_unguessable():
    d = auth.dummy_hash()
    assert d == auth.dummy_hash()
    assert auth.verify_password("password1234", d) is False


def test_tokens_are_random_and_only_hash_is_comparable():
    a, b = auth.new_token(), auth.new_token()
    assert a != b and len(a) >= 40
    assert auth.hash_token(a) == auth.hash_token(a) and auth.hash_token(a) != auth.hash_token(b)
    assert a not in auth.hash_token(a)


def test_only_specialist_may_approve_and_unknown_actions_are_denied():
    assert auth.can(auth.SPECIALIST, auth.APPROVE)
    assert not auth.can(auth.ASSISTANT, auth.APPROVE)
    for role in auth.ROLES:
        assert auth.can(role, auth.VIEW) and auth.can(role, auth.EDIT)
    assert not auth.can(auth.SPECIALIST, "delete_everything")  # deny by default
    assert not auth.can(None, auth.VIEW) and not auth.can("admin", auth.APPROVE)


def test_username_rules():
    assert auth.validate_username("  Sara.Ali ") == "sara.ali"
    for bad in ("ab", "x" * 33, "سارة", "a b", "-abc", "a@b.com", ""):
        with pytest.raises(ValueError):
            auth.validate_username(bad)


def test_display_name_and_role_rules():
    assert auth.validate_display_name("  م.   سارة ") == "م. سارة"
    for bad in ("", "س", "x" * 121, "اسم\x00خفي"):
        with pytest.raises(ValueError):
            auth.validate_display_name(bad)
    assert auth.validate_role("assistant") == "assistant"
    with pytest.raises(ValueError):
        auth.validate_role("admin")


def test_password_rules():
    assert auth.validate_password("abcdefghij") == "abcdefghij"
    for bad in ("short", " abcdefghij", "abcdefghij ", "x" * 129):
        with pytest.raises(ValueError):
            auth.validate_password(bad)
    with pytest.raises(ValueError):
        auth.validate_password("abcdefghij", min_len=12)


def test_lockout_after_max_failures_then_expires():
    failed, until = 0, None
    for i in range(4):
        failed, until = auth.register_failure(failed, NOW, max_attempts=5, lock_minutes=15)
        assert until is None and failed == i + 1
    failed, until = auth.register_failure(failed, NOW, max_attempts=5, lock_minutes=15)
    assert until == NOW + timedelta(minutes=15) and failed == 0
    assert auth.is_locked(until, NOW + timedelta(minutes=14, seconds=59))
    assert auth.minutes_left(until, NOW) == 15
    assert auth.minutes_left(until, NOW + timedelta(minutes=14, seconds=1)) == 1
    assert not auth.is_locked(until, NOW + timedelta(minutes=15))
    assert auth.minutes_left(until, NOW + timedelta(minutes=20)) == 0


def test_naive_datetimes_from_sqlite_are_treated_as_utc():
    naive = datetime(2026, 11, 21, 12, 30)
    assert auth.as_utc(naive).tzinfo is not None
    assert auth.is_locked(naive, NOW) and not auth.is_locked(None, NOW)
    assert auth.as_utc(None) is None
