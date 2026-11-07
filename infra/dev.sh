#!/usr/bin/env bash
# Run the API + boss UI locally on http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
exec uvicorn backend.app:app --reload --port "${PORT:-8000}"
