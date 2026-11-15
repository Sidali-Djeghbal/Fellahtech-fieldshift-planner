#!/usr/bin/env bash
# Run the SI Model API locally and expose it on a free public HTTPS URL via ngrok.
#
#   ./serve_public.sh                 # random ngrok URL (changes on restart)
#   ./serve_public.sh my-name.ngrok-free.app   # your free static domain
#
# Requires: .venv (created by the repo), ngrok logged in (ngrok config add-authtoken ...).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PORT="${SI_PORT:-8000}"
DOMAIN="${1:-}"

cleanup() {
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${TUNNEL_PID:-}" ]] && kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ ! -d .venv ]]; then
  echo "== creating venv (first run)"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

echo "== starting SI model API on :$PORT"
./.venv/bin/python -m uvicorn src.api.app:app --host 127.0.0.1 --port "$PORT" &
API_PID=$!

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/api/v1/health" >/dev/null; then break; fi
  sleep 1
done
curl -sf "http://127.0.0.1:$PORT/api/v1/health" >/dev/null \
  || { echo "API failed to start"; exit 1; }
echo "== API healthy"

echo "== opening ngrok tunnel"
if [[ -n "$DOMAIN" ]]; then
  ngrok http --domain="$DOMAIN" "$PORT" >/tmp/ngrok.log 2>&1 &
else
  ngrok http "$PORT" >/tmp/ngrok.log 2>&1 &
fi
TUNNEL_PID=$!

sleep 5
PUBLIC_URL="$(curl -s http://127.0.0.1:4040/api/tunnels \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["tunnels"][0]["public_url"])')"

cat <<EOF

  API (local):   http://127.0.0.1:$PORT/api/v1
  API (public):  $PUBLIC_URL/api/v1
  Docs:          $PUBLIC_URL/docs

  Deployed frontend must be built against the public URL:
    cd ../frontend
    NEXT_OUTPUT_EXPORT=true NEXT_PUBLIC_API_BASE_URL=$PUBLIC_URL npm run build
    npx wrangler deploy

  Ctrl-C stops both.
EOF

wait
