#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python manage.py makemigrations
python manage.py migrate
