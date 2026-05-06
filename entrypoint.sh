#!/bin/bash
set -e

echo "======================================"
echo " TaskBoard — Container Startup"
echo "======================================"

echo "[1/3] Running database migrations..."
python manage.py migrate --noinput

echo "[2/3] Seeding initial data..."
python manage.py seed_db

echo "[3/3] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "======================================"
echo " Starting Daphne ASGI server..."
echo "======================================"
exec "$@"
