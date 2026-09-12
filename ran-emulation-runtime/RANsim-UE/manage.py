#!/usr/bin/env python
"""RANsim-UE — Django management 指令。"""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django 安裝失敗，檢查 requirements") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
