# Troubleshooting Q&A

## Q: I uploaded a photo that clearly isn't a fish (e.g. a cat) and got back a confident species prediction instead of a rejection. Why?

**A:** The CLIP fish gate (`predictors/fish_gate.py`) failed to load at startup, and the old
behavior was to swallow that failure silently and keep serving `/predict` requests as if
nothing was wrong — every image, fish or not, was forced through the closed-set EfficientNet
classifier, which has no "not a fish" class and will always return its best guess.

The most common cause: `docker-compose.yml` mounts the Hugging Face cache read-only —

```yaml
- ~/.cache/huggingface:/root/.cache/huggingface:ro
```

— on the assumption that the CLIP weights (`openai/clip-vit-base-patch32`, ~600MB) are already
downloaded there. If that host directory is empty (fresh clone, cache wiped, `docker system
prune`, new machine, etc.), the gate tries to download the weights on startup, hits the
read-only mount, and throws `[Errno 30] Read-only file system`.

**Check `docker compose logs ai-service` for:**
```
FISH GATE FAILED TO LOAD — /predict will refuse requests until this is fixed: [Errno 30] Read-only file system: '/root/.cache/huggingface/hub'
```

**Fix — populate the cache once, then keep it read-only:**
```bash
# 1. Temporarily allow writes: edit docker-compose.yml, drop ":ro" from the
#    huggingface cache mount for the ai-service volume.
# 2. Recreate the container so it downloads and caches the weights:
docker compose up -d --force-recreate ai-service
# 3. Watch logs until you see "CLIP fish gate loaded" (not "FAILED TO LOAD"):
docker compose logs -f ai-service
# 4. Revert docker-compose.yml back to ":ro" and recreate again — it now
#    reads from the populated cache without needing write access:
docker compose up -d --force-recreate ai-service
```
The container runs as root (no `USER` directive in the `Dockerfile`), so no `chown`/`sudo` is
needed even if the host cache directory ends up owned by `root`.

**Since 2026-07-15, this failure mode is no longer silent.** If the gate fails to load:
- `GET /health` returns HTTP `503` with `{"status": "degraded", "gate_loaded": false}` instead
  of a plain `200`, so Docker's `HEALTHCHECK` (and any orchestration/monitoring watching it)
  flags the container as unhealthy immediately.
- `POST /predict` returns HTTP `503` with an explicit error instead of a fabricated species
  guess.

If you see `503`s across the board, the fix above (populate the cache) is almost certainly the
answer — check the startup logs first to confirm it's the gate and not something else.

## Q: I made a code change to `main.py` (or another Python file) and it doesn't seem to take effect when I hit the running service. Why?

**A:** `docker-compose.yml`'s `ai-service` doesn't bind-mount the source code — the `Dockerfile`
does `COPY . .` at *build* time, so the container is running a snapshot of the code baked into
the image, not a live view of your working tree.

**Fix:** rebuild the image before recreating the container:
```bash
docker compose build ai-service
docker compose up -d --force-recreate ai-service
```
`docker compose up -d` alone (without `build`) will keep using the stale image.
