#!/bin/bash
# Ombre-Brain dual-process startup
# server.py on :8000 (background), gateway.py on $PORT (foreground).
set -e

BUCKETS="${OMBRE_BUCKETS_DIR:-/data}"
STATE="${OMBRE_STATE_DIR:-/data/state}"

mkdir -p "$BUCKETS" "$STATE"

echo "=== Ombre-Brain ==="
echo "BUCKETS_DIR=$BUCKETS"
echo "STATE_DIR=$STATE"

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: neither python3 nor python found" >&2
    exit 1
fi
echo "PYTHON=$PYTHON"

health_check() {
    "$PYTHON" -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('http://127.0.0.1:${1}/health', timeout=3)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

# Start server.py (brain) in the background
echo "[start] brain :8000 ..."
"$PYTHON" server.py &
BRAIN_PID=$!

for i in $(seq 1 30); do
    if health_check 8000; then
        echo "[start] brain health OK (attempt $i)"
        break
    fi
    sleep 1
done

# Run gateway.py as the main foreground process
GATEWAY_PORT="${PORT:-8010}"
echo "[start] gateway :${GATEWAY_PORT} (foreground) ..."
exec "$PYTHON" gateway.py
