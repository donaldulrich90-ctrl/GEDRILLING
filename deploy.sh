#!/usr/bin/env bash
# Deploy / update GOOD ENGINEERS OS (Docker Compose).
# On VPS: cd /root/projets/GE-MINING && bash deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=========================================="
echo "Deploy from: $ROOT"
echo "=========================================="

if [[ ! -f app.py ]]; then
  echo "ERROR: app.py missing in $ROOT"
  exit 1
fi

SIZE="$(wc -c < app.py | tr -d ' ')"
if [[ "${SIZE}" -lt 50000 ]]; then
  echo "ERROR: app.py too small (${SIZE} bytes), expected ~600KB"
  exit 1
fi

if ! grep -q '_ensure_fleet_summary_df' app.py; then
  echo "ERROR: app.py missing _ensure_fleet_summary_df - copy app.py from your PC first."
  exit 1
fi

if [[ ! -f Dockerfile ]] || ! grep -q '_ensure_fleet_summary_df' Dockerfile; then
  echo "ERROR: Dockerfile missing or wrong - copy Dockerfile from your PC."
  exit 1
fi

echo "==> docker compose build --no-cache"
docker compose build --no-cache

echo "==> docker compose up -d"
docker compose up -d

echo "==> nginx_network (optional)"
docker network connect nginx_network good-engineers-os 2>/dev/null || true

echo "==> Streamlit health"
sleep 2
HTTP="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501/_stcore/health || true)"
if [[ "${HTTP}" != "200" ]]; then
  echo "WARNING: health HTTP ${HTTP} (expected 200). Check: docker logs good-engineers-os --tail 40"
else
  echo "OK healthcheck (${HTTP})"
fi

docker compose ps
echo "=========================================="
echo "Done. Test: curl -sI http://127.0.0.1:8501 | head -3"
echo "=========================================="
