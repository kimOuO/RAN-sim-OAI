"""Test settings — in-memory SQLite for fast unit tests."""
from main.settings.base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
