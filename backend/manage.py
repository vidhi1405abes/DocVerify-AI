"""Account administration from the command line.

    python backend/manage.py list-users
    python backend/manage.py reset-password you@example.com
    python backend/manage.py make-admin you@example.com

Run it on the computer where the backend's database lives. The app has no email service,
so this is how a forgotten password is recovered.
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from docverify.auth import MIN_PASSWORD_LENGTH
from docverify.config import default_database_url
from docverify.models import User, make_session_factory


def find_user(session, email):
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def list_users(session_factory):
    with session_factory() as session:
        users = session.scalars(select(User).order_by(User.id)).all()
    if not users:
        print("No accounts yet. The first account registered in the app becomes the admin.")
    for user in users:
        print(f"{user.email:40} {user.role:6} {user.name}")
    return 0


def reset_password(session_factory, email, new_password):
    if len(new_password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    with session_factory() as session:
        user = find_user(session, email)
        if user is None:
            print(f"No account with email {email}. Run list-users to see them.", file=sys.stderr)
            return 1
        user.password_hash = generate_password_hash(new_password)
        session.commit()
    print(f"Password updated for {email}. Sign in with the new password.")
    return 0


def make_admin(session_factory, email):
    with session_factory() as session:
        user = find_user(session, email)
        if user is None:
            print(f"No account with email {email}. Run list-users to see them.", file=sys.stderr)
            return 1
        user.role = "admin"
        session.commit()
    print(f"{email} is now an administrator.")
    return 0


def ask_new_password():
    first = getpass.getpass("New password (hidden): ")
    if first != getpass.getpass("Type it again: "):
        print("Passwords do not match.", file=sys.stderr)
        return None
    return first


def main(argv=None):
    parser = argparse.ArgumentParser(description="DocVerify AI account administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-users", help="show every account")
    reset = commands.add_parser("reset-password", help="set a new password for an account")
    reset.add_argument("email")
    admin = commands.add_parser("make-admin", help="give an account administrator rights")
    admin.add_argument("email")
    args = parser.parse_args(argv)

    session_factory = make_session_factory(default_database_url())
    if args.command == "list-users":
        return list_users(session_factory)
    if args.command == "make-admin":
        return make_admin(session_factory, args.email)
    password = ask_new_password()
    return 1 if password is None else reset_password(session_factory, args.email, password)


if __name__ == "__main__":
    sys.exit(main())
