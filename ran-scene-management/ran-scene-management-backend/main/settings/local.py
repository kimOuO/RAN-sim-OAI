"""Development settings."""
from main.settings.base import *  # noqa: F401,F403

# 2026-09-16:DEBUG 會讓每條 DB 連線保留最近 9000 筆 SQL 原文,長壽背景執行緒(歸檔大 JSON)因此吃掉數百 MB。
# compose 對長時間運作的服務設 DJANGO_DEBUG=False;本機開發沒設時照舊開。
from main.utils.env_loader import get_bool  # noqa: E402
DEBUG = get_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["*"]
