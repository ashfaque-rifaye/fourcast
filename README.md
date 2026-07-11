# AMDHack — Team mindflayer

> AMD Developer Hackathon: ACT II — Track 3 (Unicorn). Built on AMD Instinct MI300X + Fireworks AI (AMD-hosted models) + Gemma.

**[Project name + one-line pitch land here once the concept is locked.]**

## Architecture

- `app/` — FastAPI service; every LLM call routed through `app/fireworks.py`
  - **Fireworks AI serverless** (AMD-hardware-hosted models, Gemma family) — default backend
  - **Self-hosted vLLM on AMD MI300X** (AMD Developer Cloud) — optional second backend via `AMD_VLLM_BASE_URL`
- `scripts/smoke_test.py` — end-to-end environment verification
- Containerized: `Dockerfile` + `docker-compose.yml`; CI builds and pushes to GHCR on every push

## Quickstart

```bash
cp .env.example .env       # add your FIREWORKS_API_KEY
docker compose up --build  # serves on http://localhost:8000
```

Without Docker:

```bash
uv venv && uv pip install -r requirements.txt
uv run python scripts/smoke_test.py     # verify credentials + models
uv run uvicorn app.main:app --reload    # http://localhost:8000/health
```

## Environment variables

| Var | Required | Purpose |
| --- | --- | --- |
| `FIREWORKS_API_KEY` | yes | Fireworks AI inference (create at app.fireworks.ai → Settings → API Keys) |
| `FIREWORKS_MODEL` | no | Default model id (defaults to Gemma 3 27B IT) |
| `AMD_VLLM_BASE_URL` | no | OpenAI-compatible endpoint of self-hosted vLLM on MI300X |

## AMD platform usage

[How MI300X / ROCm / Fireworks-on-AMD are load-bearing in this project — filled in with the final architecture.]
