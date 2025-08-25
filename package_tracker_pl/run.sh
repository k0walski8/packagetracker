#!/usr/bin/with-contenv bash
set -euo pipefail
export PYTHONUNBUFFERED=1
# Activate venv created during build
. /opt/venv/bin/activate
exec python -m uvicorn main:app --host 0.0.0.0 --port 8099
