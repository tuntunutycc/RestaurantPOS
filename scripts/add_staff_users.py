#!/usr/bin/env python3
"""
Add staff users (waiter, kitchen, cashier) so they can log in with PIN at /pin-login.

Run from project root:
  python scripts/add_staff_users.py

Creates users with unique usernames and 4-digit PINs. Change the list below to add
or modify staff. PINs must be exactly 4 digits and unique across all users.
"""
import sys
from pathlib import Path

# Add project root so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal
from models import User
from auth import hash_password

# Staff to create: (username, role, pin_code)
# role must be: waiter | kitchen | cashier
# pin_code must be exactly 4 digits, unique
STAFF = [
    ("waiter1", "waiter", "1111"),
    ("waiter2", "waiter", "2222"),
    ("kitchen1", "kitchen", "3333"),
    ("cashier1", "cashier", "4444"),
]


def main():
    db = SessionLocal()
    try:
        for username, role, pin_code in STAFF:
            if len(pin_code) != 4 or not pin_code.isdigit():
                print(f"Skip {username}: pin_code must be 4 digits, got {pin_code!r}")
                continue
            existing = db.query(User).filter(
                (User.username == username) | (User.pin_code == pin_code)
            ).first()
            if existing:
                print(f"Already exists: {username} (or PIN {pin_code} taken), skipping")
                continue
            user = User(
                username=username,
                password_hash=hash_password("changeme"),  # staff use PIN; set if they need /login
                role=role,
                pin_code=pin_code,
            )
            db.add(user)
            print(f"Created: {username} role={role} PIN={pin_code}")
        db.commit()
        print("Done. Staff can log in at /pin-login with their PIN.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
