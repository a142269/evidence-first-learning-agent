"""Trusted host CLI for initial teacher provisioning and V2 course grants."""
from __future__ import annotations

import argparse
import getpass
import os


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create-teacher", "grant", "revoke"])
    parser.add_argument("account")
    parser.add_argument("--course")
    parser.add_argument("--display-name", default="")
    args = parser.parse_args(argv)
    if not os.environ.get("DATABASE_URL"):
        parser.error("Set DATABASE_URL explicitly for the intended migrated database")
    if not 3 <= len(args.account.strip()) <= 32:
        parser.error("account length must be 3..32")
    if args.action != "create-teacher" and (not args.course or not 1 <= len(args.course.strip()) <= 128):
        parser.error("grant/revoke requires --course (1..128 characters)")
    from backend.app.core.passwords import hash_password
    from backend.app.repositories.account_repo import AccountRepository, StoredAccount
    from backend.app.repositories.auth_repo import AuthRepository

    try:
        if args.action == "create-teacher":
            password = getpass.getpass("New teacher password (12+ characters): ")
            confirmation = getpass.getpass("Repeat password: ")
            if len(password.strip()) < 12 or password != password.strip() or password != confirmation:
                parser.error("Passwords must match, be 12+ characters, and have no surrounding whitespace")
            AccountRepository().upsert(StoredAccount(account=args.account.strip(),
                password_hash=hash_password(password), role="teacher",
                display_name=args.display_name.strip()[:128] or args.account.strip()), create_only=True)
        elif args.action == "grant":
            AuthRepository().grant_course(args.account.strip(), args.course.strip())
        else:
            AuthRepository().revoke_course(args.account.strip(), args.course.strip())
    except Exception as exc:
        # Drivers may include connection strings or SQL parameters in exception text.
        parser.exit(1, f"Operation failed ({type(exc).__name__}); check account and database configuration.\n")
    print("Access operation completed.")


if __name__ == "__main__":
    main()
