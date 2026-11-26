"""Account validation and password hashing."""

import re

from werkzeug.security import check_password_hash, generate_password_hash

# No "@" is allowed, so a username can never be mistaken for an email address.
USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,30}")
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PASSWORD_MIN = 8
PASSWORD_MAX = 128


def clean_login(value):
    """Usernames and emails are compared without spaces or capital letters."""
    return value.strip().lower()


def validate_registration(username, email, password, confirm_password):
    """Return an error message, or None when every field is acceptable."""
    if not USERNAME_PATTERN.fullmatch(username):
        return "Username must be 3–30 characters: letters, numbers or underscores."
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return "Enter a valid email address."
    if len(password) < PASSWORD_MIN or len(password) > PASSWORD_MAX:
        return "Password must be " + str(PASSWORD_MIN) + "–" + str(PASSWORD_MAX) + " characters."
    if password != confirm_password:
        return "The two passwords do not match."
    return None


def hash_password(password):
    """Return a salted hash. Only this value is stored in the database."""
    return generate_password_hash(password)


def password_is_correct(password_hash, password):
    return check_password_hash(password_hash, password)
