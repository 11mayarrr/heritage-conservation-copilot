"""Create and manage the team's accounts (there is no public sign-up page).

Run from the repository root, with the virtual environment active:

    python scripts/manage_users.py create            # asks for each value
    python scripts/manage_users.py list
    python scripts/manage_users.py set-password --username sara
    python scripts/manage_users.py deactivate --username sara
    python scripts/manage_users.py activate --username sara

Passwords are typed at a hidden prompt, never on the command line, so they do not
end up in the terminal history. Roles: assistant (مساعد) uploads and edits;
specialist (مختص) is the only role that may approve.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.engine import make_url  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import session as dbs  # noqa: E402
from app.services import accounts, auth  # noqa: E402


def _ask_password(ask_secret, min_len: int) -> str:
    first = ask_secret(f"كلمة السر ({min_len} أحرف على الأقل): ")
    auth.validate_password(first, min_len)
    if ask_secret("أعد كتابة كلمة السر: ") != first:
        raise ValueError("كلمتا السر غير متطابقتين.")
    return first


def _ask_role(ask) -> str:
    choice = ask("الدور: 1 = مساعد (يرفع ويعدّل)، 2 = مختص (يعتمد) ← ").strip()
    if choice not in ("1", "2"):
        raise ValueError("اختر 1 أو 2.")
    return auth.ASSISTANT if choice == "1" else auth.SPECIALIST


def main(argv=None, *, ask=input, ask_secret=getpass.getpass, out=print) -> int:
    p = argparse.ArgumentParser(description="إدارة حسابات الفريق")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="إنشاء حساب")
    c.add_argument("--username")
    c.add_argument("--name", help="الاسم الظاهر في السجل والتقارير")
    c.add_argument("--role", choices=auth.ROLES)
    sub.add_parser("list", help="عرض الحسابات")
    for name, help_ in (("set-password", "تغيير كلمة سر"), ("deactivate", "إيقاف حساب"), ("activate", "تفعيل حساب")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--username")
    args = p.parse_args(argv)

    s = get_settings()
    dbs.init_engine()
    out(f"قاعدة البيانات: {make_url(s.database_url).render_as_string(hide_password=True)}")
    db = next(dbs.get_db())
    try:
        if args.cmd == "list":
            users = accounts.list_users(db)
            if not users:
                out("لا توجد حسابات بعد. أنشئ أول حساب بالأمر: python scripts/manage_users.py create")
            for u in users:
                state = "" if u.is_active else "  [موقوف]"
                out(f"{u.username:<20} {auth.ROLE_AR.get(u.role, u.role):<8} {u.display_name}{state}")
            return 0

        username = args.username or ask("اسم المستخدم (إنجليزي صغير، للدخول): ")
        if args.cmd == "create":
            name = args.name or ask("الاسم الظاهر (يُكتب في سجل التعديلات والتقارير): ")
            role = args.role or _ask_role(ask)
            password = _ask_password(ask_secret, s.min_password_length)
            u = accounts.create_user(
                db, username=username, display_name=name, role=role, password=password,
                min_password_length=s.min_password_length,
            )
            out(f"تم إنشاء الحساب: {u.username} ({auth.ROLE_AR[u.role]}) باسم «{u.display_name}».")
        elif args.cmd == "set-password":
            password = _ask_password(ask_secret, s.min_password_length)
            u = accounts.set_password(db, username, password, s.min_password_length)
            out(f"تم تغيير كلمة سر {u.username}، وأُنهيت جلساته المفتوحة.")
        else:
            active = args.cmd == "activate"
            u = accounts.set_active(db, username, active)
            out(f"تم {'تفعيل' if active else 'إيقاف'} الحساب {u.username}.")
        return 0
    except ValueError as e:
        out(f"لم يتم: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
