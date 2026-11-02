"""Site administration from the command line (run from backend/).

    python -m app.cli make-admin owner@example.com      # give an existing account admin access
    python -m app.cli create-admin you@example.com "Your Name"   # new account in an "Operators" workspace
    python -m app.cli revoke-admin someone@example.com
    python -m app.cli list-admins
    python -m app.cli clear-team             # remove every About-page team member and photo

Admin access is never granted through the website's sign-up, only here or by another admin.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from .db import init_engine, session_factory
from .models import Organization, User
from .security import hash_password


def _find(db, email: str) -> User:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        sys.exit(f"No account with email {email!r}. Sign up on the website first, or use create-admin.")
    return user


def make_admin(email: str) -> None:
    with session_factory()() as db:
        user = _find(db, email)
        user.is_admin, user.is_active = True, True
        db.commit()
        print(f"{user.email} is now a site administrator. Sign in and open /admin.")


def revoke_admin(email: str) -> None:
    with session_factory()() as db:
        user = _find(db, email)
        if user.is_admin and db.query(User).filter(User.is_admin.is_(True)).count() == 1:
            sys.exit("Refusing to remove the last administrator.")
        user.is_admin = False
        db.commit()
        print(f"{user.email} is no longer an administrator.")


def create_admin(email: str, name: str) -> None:
    email = email.strip().lower()
    with session_factory()() as db:
        if db.query(User).filter(User.email == email).first():
            sys.exit(f"{email} already has an account; use make-admin instead.")
        password = getpass.getpass("Password (at least 8 characters): ")
        if len(password) < 8 or len(password.encode("utf-8")) > 72:
            sys.exit("Password must be 8 to 72 bytes long.")
        if getpass.getpass("Repeat password: ") != password:
            sys.exit("Passwords don't match.")
        org = Organization(name="Operators")
        db.add_all([org, User(organization=org, email=email, name=name.strip() or email, role="owner",
                              password_hash=hash_password(password), is_admin=True)])
        db.commit()
        print(f"Created administrator {email}. Sign in and open /admin.")


def clear_team() -> None:
    from .config import get_settings
    from .models import TeamMember

    with session_factory()() as db:
        members = db.query(TeamMember).all()
        for m in members:
            if m.photo_path:
                (get_settings().data_dir / m.photo_path).unlink(missing_ok=True)
            db.delete(m)
        db.commit()
        print(f"Removed {len(members)} team member(s) from the About page.")


def list_admins() -> None:
    with session_factory()() as db:
        admins = db.query(User).filter(User.is_admin.is_(True)).order_by(User.id).all()
        for u in admins:
            print(f"{u.email}\t{u.name}\t{'active' if u.is_active else 'disabled'}")
        if not admins:
            print("No administrators yet. Run: python -m app.cli make-admin <email>")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Churn Service site administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("make-admin", help="give an existing account admin access").add_argument("email")
    sub.add_parser("revoke-admin", help="remove admin access").add_argument("email")
    create = sub.add_parser("create-admin", help="create a new admin account (asks for a password)")
    create.add_argument("email")
    create.add_argument("name", nargs="?", default="")
    sub.add_parser("list-admins", help="list administrators")
    sub.add_parser("clear-team", help="remove every About-page team member and photo")
    args = parser.parse_args(argv)
    init_engine()
    {"make-admin": lambda: make_admin(args.email), "revoke-admin": lambda: revoke_admin(args.email),
     "create-admin": lambda: create_admin(args.email, args.name), "list-admins": list_admins,
     "clear-team": clear_team}[args.command]()


if __name__ == "__main__":
    main()
