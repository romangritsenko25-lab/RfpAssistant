"""Command-line user management: ``python -m rfp.users add <username> [--admin]``."""

import argparse
import getpass
import sys

from rfp import db
from rfp.auth import create_user
from rfp.services.errors import ServiceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rfp.users", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="create a user; the password is asked for interactively")
    add.add_argument("username")
    add.add_argument("--admin", action="store_true", help="grant administrator rights")
    args = parser.parse_args(argv)

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    conn = db.connect()
    try:
        db.apply_schema(conn)
        create_user(conn, args.username, password, is_admin=args.admin)
    except ServiceError as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"User '{args.username}' created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
