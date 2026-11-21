"""Login, sessions, roles and the account command (needs the web stack)."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from app.services import accounts, auth  # noqa: E402

PASSWORD = "test-pass-1234"
LOGIN = "/api/auth/login"
GOOD = {"username": "huda", "password": PASSWORD}
BAD = {"username": "huda", "password": "wrong-password-1"}


@pytest.fixture()
def anon(client):
    """A second browser on the same server: no cookies, so not signed in."""
    return TestClient(client.app)


@pytest.fixture()
def db(client):
    from app.database.session import get_db

    d = next(get_db())
    yield d
    d.close()


def _upload_as(c, samples, code="W-AUTH"):
    w = c.post("/api/walls", json={"code": code, "building_name": "مثال"})
    assert w.status_code == 201, w.text
    with open(samples / "synthetic_wall_T1.jpg", "rb") as f:
        r = c.post("/api/inspections", data={"wall_id": w.json()["id"]}, files={"image": ("t.jpg", f, "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def test_every_route_needs_login_except_login_and_health(anon):
    for method, path in [
        ("get", "/api/walls"), ("get", "/api/inspections"), ("get", "/api/audit"), ("get", "/api/knowledge"),
        ("get", "/api/knowledge/damage-types"), ("get", "/api/comparisons"), ("get", "/api/auth/me"),
        ("get", "/api/inspections/none/image.jpg"), ("post", "/api/walls"), ("post", "/api/inspections/none/approve"),
    ]:
        r = getattr(anon, method)(path)
        assert r.status_code == 401, (method, path, r.status_code)
        assert r.json()["detail"] == auth.NOT_LOGGED_IN_AR
    assert anon.get("/api/health").status_code == 200
    assert anon.post(LOGIN, json=BAD).status_code == 401  # reachable without a session


def test_login_sets_httponly_cookie_and_me_works_then_logout_ends_it(anon):
    r = anon.post(LOGIN, json=GOOD)
    assert r.status_code == 200
    assert r.json() == {"username": "huda", "display_name": "هدى", "role": "assistant", "role_ar": "مساعد"}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "hcc_session=" in cookie
    assert "password" not in r.text.lower()
    token = anon.cookies.get("hcc_session")
    assert anon.get("/api/auth/me").json()["display_name"] == "هدى"

    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/auth/me").status_code == 401
    # The old cookie value is dead on the server too, not only deleted in the browser.
    thief = TestClient(anon.app)
    thief.cookies.set("hcc_session", token)
    assert thief.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_user_get_the_same_answer(anon):
    a = anon.post(LOGIN, json=BAD)
    b = anon.post(LOGIN, json={"username": "nobody", "password": "whatever-123"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"detail": auth.BAD_LOGIN_AR}
    assert "set-cookie" not in a.headers


def test_username_is_case_insensitive_but_password_is_not(anon):
    assert anon.post(LOGIN, json={"username": " HUDA ", "password": PASSWORD}).status_code == 200
    assert TestClient(anon.app).post(LOGIN, json={"username": "huda", "password": PASSWORD.upper()}).status_code == 401


def test_account_locks_after_repeated_failures(anon):
    for _ in range(4):
        assert anon.post(LOGIN, json=BAD).status_code == 401
    r = anon.post(LOGIN, json=BAD)
    assert r.status_code == 429 and "دقيقة" in r.json()["detail"]
    assert anon.post(LOGIN, json=GOOD).status_code == 429  # even the right password, while locked


def test_a_successful_login_resets_the_failure_counter(anon):
    for _ in range(3):
        anon.post(LOGIN, json=BAD)
    assert anon.post(LOGIN, json=GOOD).status_code == 200
    for _ in range(4):
        assert anon.post(LOGIN, json=BAD).status_code == 401  # a fresh set of 4, not 1


def test_expired_session_is_refused(db):
    user = accounts.authenticate(db, "huda", PASSWORD)
    past = datetime.now(timezone.utc) - timedelta(hours=5)
    token = accounts.open_session(db, user, 1, now=past)
    assert accounts.user_for_token(db, token, now=past + timedelta(minutes=59)) is not None
    assert accounts.user_for_token(db, token) is None


def test_deactivating_or_changing_password_ends_sessions(anon, db):
    assert anon.post(LOGIN, json=GOOD).status_code == 200
    accounts.set_active(db, "huda", False)
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.post(LOGIN, json=GOOD).status_code == 401
    accounts.set_active(db, "huda", True)

    assert anon.post(LOGIN, json=GOOD).status_code == 200
    accounts.set_password(db, "huda", "a-brand-new-pass-9")
    assert anon.get("/api/auth/me").status_code == 401
    assert TestClient(anon.app).post(LOGIN, json=GOOD).status_code == 401
    assert TestClient(anon.app).post(LOGIN, json={"username": "huda", "password": "a-brand-new-pass-9"}).status_code == 200


def test_assistant_can_work_but_not_approve_and_specialist_can(client, anon, samples):
    assert anon.post(LOGIN, json=GOOD).status_code == 200  # huda, assistant
    insp = _upload_as(anon, samples)
    iid = insp["id"]
    crack = next(r for r in insp["regions"] if r["damage_type"] == "crack")

    # Assistant edits are allowed...
    assert anon.patch(f"/api/inspections/{iid}/regions/{crack['id']}", json={"note": "ملاحظة المساعد"}).status_code == 200
    # ...approvals are not.
    r = anon.post(f"/api/inspections/{iid}/approve", json={})
    assert r.status_code == 403 and r.json()["detail"] == auth.APPROVE_FORBIDDEN_AR
    assert anon.post(f"/api/inspections/{iid}/regions/{crack['id']}/approve", json={}).status_code == 403
    assert client.get(f"/api/inspections/{iid}").json()["status"] == "in_review"

    # The specialist (the `client` fixture) can; a typed name in the old header is ignored.
    forged = {"X-User-Name": quote("مزوّر")}
    r = client.post(f"/api/inspections/{iid}/approve", json={"reason": "مراجعة"}, headers=forged)
    assert r.status_code == 200
    assert r.json()["status"] == "approved" and r.json()["approved_by"] == "م. سارة"

    log = client.get("/api/audit", params={"inspection_id": iid}).json()
    users = {e["user"] for e in log}
    assert "مزوّر" not in users
    assert {"هدى", "م. سارة"} <= users
    assert next(e for e in log if e["action"] == "approve")["user"] == "م. سارة"
    assert any(e["user"] == "هدى" and e["action"] == "update" for e in log)  # the assistant's edit is attributed to her


def test_account_command_creates_accounts_that_can_log_in(client, anon, db):
    import manage_users

    said = []
    answers = iter(["new.person", "أ. منى", "2"])
    secrets = iter(["long-enough-pass-1", "long-enough-pass-1"])
    code = manage_users.main(["create"], ask=lambda _p: next(answers), ask_secret=lambda _p: next(secrets), out=said.append)
    assert code == 0 and any("أ. منى" in line for line in said)
    r = anon.post(LOGIN, json={"username": "new.person", "password": "long-enough-pass-1"})
    assert r.status_code == 200 and r.json()["role"] == "specialist"

    # Taken username, taken display name, mismatched or short password: nothing is created.
    for args, secret_list in [
        (["create", "--username", "huda", "--name", "اسم آخر", "--role", "assistant"], ["long-enough-pass-1"] * 2),
        (["create", "--username", "other.one", "--name", "هدى", "--role", "assistant"], ["long-enough-pass-1"] * 2),
        (["create", "--username", "other.one", "--name", "شخص", "--role", "assistant"], ["long-enough-pass-1", "different-pass-22"]),
        (["create", "--username", "other.one", "--name", "شخص", "--role", "assistant"], ["short"]),
    ]:
        it = iter(secret_list)
        out = []
        assert manage_users.main(args, ask=lambda _p: "", ask_secret=lambda _p: next(it), out=out.append) == 1
        assert any("لم يتم" in line for line in out)
    assert accounts.list_users(db) and all(u.username != "other.one" for u in accounts.list_users(db))

    lines = []
    assert manage_users.main(["list"], out=lines.append) == 0
    assert any("sara" in line for line in lines) and not any("password" in line.lower() for line in lines)
