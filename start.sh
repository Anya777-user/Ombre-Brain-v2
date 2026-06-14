#!/bin/bash
# Ombre-Brain Railway — Dual-process startup
# Runs server.py (:8000) and gateway.py (:8010) in one container.
# Uses Python stdlib urllib for health checks (no curl in python:3.12-slim).
set -e

BUCKETS="${OMBRE_BUCKETS_DIR:-/data}"
STATE="${OMBRE_STATE_DIR:-/data/state}"

mkdir -p "$BUCKETS" "$STATE"

echo "=== Ombre-Brain Railway ==="
echo "BUCKETS_DIR=$BUCKETS"
echo "STATE_DIR=$STATE"

health_check() {
    python3 -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('http://127.0.0.1:${1}/health', timeout=3)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

echo "[start] brain :8000 ..."
python3 server.py &
BRAIN_PID=$!

for i in $(seq 1 30); do
    if health_check 8000; then
        echo "[start] brain health OK (attempt $i)"
        break
    fi
    sleep 1
done

echo "[start] gateway :8010 ..."
python3 gateway.py &
GATEWAY_PID=$!

for i in $(seq 1 30); do
    if health_check 8010; then
        echo "[start] gateway health OK (attempt $i)"
        break
    fi
    sleep 1
done

echo "=== Ready ==="
echo "Brain   : http://0.0.0.0:8000"
echo "Gateway : http://0.0.0.0:8010"

wait -n
