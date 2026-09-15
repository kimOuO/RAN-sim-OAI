"""Production settings — strict ALLOWED_HOSTS, DEBUG off."""
from main.settings.base import *  # noqa: F401,F403
from main.utils.env_loader import get_list

DEBUG = False
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=[])
