# Deploying the SI Model for free (Hugging Face Spaces)

The SI model is a Python FastAPI app with a GEOS/GDAL stack (geopandas, rasterio,
shapely). That **cannot** run on Cloudflare Workers, and Cloudflare Containers are
paid — so the free host that actually fits is a **Hugging Face Docker Space**:
2 vCPU / 16 GB RAM, no credit card, public HTTPS URL, 16 GB image limit.

## 1. Get a token (30 seconds)

https://huggingface.co/settings/tokens → **New token** → role **Write** → copy `hf_...`

## 2. Deploy

```bash
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx
cd Feild-Shift-SI-Model
./deploy_hf_space.sh <your-hf-username> fieldshift-si-model
```

The script creates the Space, uploads the model (minus `.venv`, `.git`, `__pycache__`),
adds the required Docker front-matter, and triggers the build.

**First build takes ~5–10 min** (geospatial wheels). Watch it at
`https://huggingface.co/spaces/<user>/fieldshift-si-model`.

## 3. Verify

```bash
curl https://<user>-fieldshift-si-model.hf.space/api/v1/health
```

Expected: `{"status":"ok","service":"FieldShift-PhaseL-API",...}`

Interactive API docs: `https://<user>-fieldshift-si-model.hf.space/docs`

## 4. Connect the frontend

The frontend is a **static export**, so the API URL is baked in at build time:

```bash
cd frontend
NEXT_OUTPUT_EXPORT=true \
NEXT_PUBLIC_API_BASE_URL=https://<user>-fieldshift-si-model.hf.space \
npm run build
npx wrangler deploy
```

`wrangler.jsonc` already declares the `fieldshift-planner` worker with `./out` as
static assets, so this updates https://fieldshift-planner.sidalidjeghbal.workers.dev/.

CORS is already `allow_origins=["*"]` on the API, so no extra config is needed.

## Caveats of the free tier

| Thing | Behaviour |
|---|---|
| Cold start | Space sleeps after ~48 h idle; first request takes 30–60 s |
| Storage | Container filesystem is ephemeral — SQLite analyses reset on restart |
| Memory | 16 GB is plenty; 2 vCPU makes a full analyze ~5–15 s |
| Private data | The Space is public unless you make it private (private Spaces need a token from the browser) |

## Alternatives if you need it always-on

- **Oracle Cloud Always Free** VM (4 ARM cores / 24 GB) + `docker compose up` — no sleep, needs a card for signup.
- **Google Cloud Run** free tier — scales to zero, needs billing enabled.
- **Cloudflare Containers** — easiest to keep in the same account, but requires the paid Workers plan (~$5/mo).
