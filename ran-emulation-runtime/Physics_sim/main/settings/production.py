from main.settings.base import *  # noqa
from main.utils.env_loader import get_list


DEBUG = False
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=[])
