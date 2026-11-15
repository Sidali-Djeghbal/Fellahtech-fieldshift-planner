#!/usr/bin/env bash
# Deploy the Field Shift SI Model (FastAPI) to a free Hugging Face Docker Space.
#
# Usage:
#   export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
#   ./deploy_hf_space.sh <hf-username> [space-name]
#
# Get a token (write scope) at: https://huggingface.co/settings/tokens
# Resulting API base: https://<hf-username>-<space-name>.hf.space
set -euo pipefail

HF_USER="${1:-}"
SPACE_NAME="${2:-fieldshift-si-model}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "$HF_USER" ]]; then
  echo "usage: HF_TOKEN=... $0 <hf-username> [space-name]" >&2
  exit 1
fi
if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "error: HF_TOKEN is not set. Create one at https://huggingface.co/settings/tokens" >&2
  exit 1
fi

python3 -m pip install --quiet --upgrade "huggingface_hub>=0.27" >/dev/null

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "== staging files from $SRC_DIR"
rsync -a \
  --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.pytest_cache/' --exclude='*.pyc' \
  --exclude='data/app_state/' \
  "$SRC_DIR"/ "$STAGE"/

# The model's own README documents the repo; the Space needs YAML front matter.
if [[ -f "$STAGE/README.md" ]]; then
  mv "$STAGE/README.md" "$STAGE/README_MODEL.md"
fi

cat > "$STAGE/README.md" <<EOF
---
title: Field Shift SI Model
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 8000
pinned: false
license: mit
---

# Field Shift — SI Model API (FastAPI)

Guelma crop-rotation decision-support API. Free-tier deployment of the
\`Feild-Shift-SI-Model\` service.

- Health: \`/api/v1/health\`
- OpenAPI: \`/docs\`
EOF

# Model's original Dockerfile already listens on 0.0.0.0:8000 with a healthcheck.
# Spaces build the Dockerfile at the repo root, so reuse it as-is.

echo "== creating/updating Space $HF_USER/$SPACE_NAME"
HF_USER="$HF_USER" SPACE_NAME="$SPACE_NAME" STAGE="$STAGE" python3 - <<'PY'
import os
from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
repo_id = f'{os.environ["HF_USER"]}/{os.environ["SPACE_NAME"]}'
url = api.create_repo(
    repo_id=repo_id,
    repo_type="space",
    space_sdk="docker",
    exist_ok=True,
)
print(f"repo: {url}")
api.upload_folder(
    repo_id=repo_id,
    repo_type="space",
    folder_path=os.environ["STAGE"],
    commit_message="Deploy Field Shift SI Model API",
)
print(f"uploaded -> {url}")
PY

echo
echo "Space:  https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
echo "API:    https://$HF_USER-$SPACE_NAME.hf.space/api/v1/health"
echo
echo "First build takes ~5-10 min (geospatial wheels). Then wire the frontend:"
echo "  cd ../../frontend"
echo "  NEXT_OUTPUT_EXPORT=true NEXT_PUBLIC_API_BASE_URL=https://$HF_USER-$SPACE_NAME.hf.space npm run build"
echo "  npx wrangler deploy"
