"""pytest 全域 fixture 設定 — DJANGO_SETTINGS_MODULE 預設 main.settings.test。"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.test")
