#!/usr/bin/env bash
# Version courte : rebuild Docker sans verifier app.py (WinSCP ou copier ce fichier seul).
set -euo pipefail
cd "$(dirname "$0")"
docker compose build --no-cache
docker compose up -d
docker network connect nginx_network good-engineers-os 2>/dev/null || true
echo "OK. Health:" 
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8501/_stcore/health || true
