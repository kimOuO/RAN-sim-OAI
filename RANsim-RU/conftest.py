"""Pytest 啟動：把 repo root 加入 sys.path，並讓 Django 走 test settings。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.test")
