#!/usr/bin/env bash
# Initial bootstrap: create migrations, apply them, create superuser-less DB.
set -euo pipefail

cd "$(dirname "$0")/.."

python manage.py makemigrations cu_cp cu_up
python manage.py migrate
echo "RANsim-CU bootstrap complete."
