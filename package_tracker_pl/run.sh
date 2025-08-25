#!/usr/bin/with-contenv bash
set -euo pipefail

export PYTHONUNBUFFERED=1

if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
  export SUPERVISOR_TOKEN
fi

exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8099
