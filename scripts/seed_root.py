#!/usr/bin/env python3
"""
Create the initial root user when none exists.

Production-safe bootstrap: run from shell/CI, not via public UI.

Usage:
  PYTHONPATH=. python scripts/seed_root.py --username root --password 'YourSecurePass123'
  PYTHONPATH=. python scripts/seed_root.py --username root  # prompts for password

Exits 0 if root already exists (idempotent). Exits 1 on validation or DB errors.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from auth import hash_password
from database import SessionLocal
from models import User
from rbac import ROLE_ROOT


def root_exists(db=None) -> bool:
    owns_db = db is None
    if db is None:
        db = SessionLocal()
    try:
        return (
            db.query(User)
            .filter(User.role == ROLE_ROOT, User.is_deleted.is_(False))
            .first()
            is not None
        )
    finally:
        if owns_db:
            db.close()


def seed_root(username: str, password: str, db=None) -> User:
    username = username.strip().lower()
    if not username:
        raise ValueError("username is required")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")

    owns_db = db is None
    if db is None:
        db = SessionLocal()
    try:
        if root_exists(db):
            existing = (
                db.query(User)
                .filter(User.role == ROLE_ROOT, User.is_deleted.is_(False))
                .first()
            )
            print(f"Root already exists (username={existing.username}, id={existing.id}). No changes made.")
            return existing

        if db.query(User).filter(User.username == username, User.is_deleted.is_(False)).first():
            raise ValueError(f"username '{username}' is already taken by a non-root user")

        user = User(
            username=username,
            role=ROLE_ROOT,
            password_hash=hash_password(password),
            pin_code=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created root user: username={user.username}, id={user.id}")
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_db:
            db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the initial root user if none exists.")
    parser.add_argument(
        "--username",
        default="root",
        help="Root username (default: root)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Root password (min 6 chars). If omitted, prompts securely.",
    )
    args = parser.parse_args(argv)

    password = args.password
    if not password:
        password = getpass.getpass("Root password (min 6 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    try:
        seed_root(args.username, password)
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to seed root: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
