#!/usr/bin/env bash
# Render build command. Runs on every deploy.
set -o errexit

pip install -r requirements.txt

# Collect hashed static files for WhiteNoise to serve.
python manage.py collectstatic --no-input

# Apply migrations against Neon.
python manage.py migrate
