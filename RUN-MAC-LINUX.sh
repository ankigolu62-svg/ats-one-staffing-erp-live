#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else
  echo "Python 3.11+ is required. Install Python once, then rerun this script." >&2
  exit 1
fi
exec "$PY" server.py --host 127.0.0.1 --port 8765 --open
