from main.settings.base import *  # noqa: F401,F403
from main.utils.env_loader import base_dir, get_str

DEBUG = True

# 本機開發若沒 postgres,允許 DB_HOST=sqlite 退回 file SQLite。
if get_str("DB_HOST", "postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(base_dir() / "logs" / "du-local.sqlite3"),
        },
    }
