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

# The free plan has no shell, so the first admin login has to be made here.
# Set DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD in the dashboard. This is
# left in place: once the account exists createsuperuser fails on the unique
# username, which the `|| true` swallows, so later deploys are a no-op. It
# never resets an existing password.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --noinput || true
fi
