"""
Create an initial Admin account.

Run from the project root:

    python -m scripts.create_admin

Never pass passwords as command-line arguments.
"""

from getpass import getpass

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.session import (
    create_database_engine,
    create_session_factory,
)
from app.services.admin.auth import create_admin_user


def main() -> None:
    settings = get_settings()

    print("The Invisible Healer - Admin Provisioning")
    print("-----------------------------------------")

    email = input("Admin email: ").strip()
    full_name = input("Full name: ").strip()

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords do not match.")
        return

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as db:
            try:
                user = create_admin_user(
                    db,
                    email=email,
                    full_name=full_name,
                    password=password,
                )

                db.commit()

            except (ValueError, IntegrityError) as exc:
                db.rollback()

                if isinstance(exc, IntegrityError):
                    print("Could not create account.")
                else:
                    print(f"Validation error: {exc}")

                return

        print("Admin account created successfully.")
        print(f"Admin ID: {user.id}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
