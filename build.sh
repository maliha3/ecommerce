#!/usr/bin/env bash
# Render build command. Runs on every deploy.
set -o errexit

pip install -r requirements.txt

# Collect hashed static files for WhiteNoise to serve.
python manage.py collectstatic --no-input

# Apply migrations against Neon.
python manage.py migrate

# First deploy only: fill an empty database with the mock catalogue and
# generated product photos. The free plan has no shell, so this is the way in.
# Set SEED_DATA=true in the Render dashboard, deploy once, then remove it —
# leaving it on would overwrite price and stock edits made in the admin on
# every later deploy.
if [ "${SEED_DATA:-}" = "true" ]; then
  python manage.py seed_data --images
fi
