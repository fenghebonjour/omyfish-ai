# omyfish-ai

Standalone AI microservice for the OMyFish platform. Exposes a single HTTP endpoint that identifies fish species from an image. Shared by all three OMyFish projects.

## Project Family

| Repo | Role |
|---|---|
| [omyfish-python](https://github.com/fenghebonjour/omyfish-python) | Python origin — Streamlit + FastAPI, deployed on HuggingFace Spaces |
| [omyfish-dotnet](https://github.com/fenghebonjour/omyfish-dotnet) | .NET 10 enterprise rewrite — Clean Architecture + CQRS |
| [omyfish-java](https://github.com/fenghebonjour/omyfish-java) | Java 21 enterprise rewrite — Hexagonal Architecture + Event-Driven |
| **omyfish-ai** (this) | Shared AI microservice — used by all three above |

## API

```
POST /predict
Content-Type: application/json

{
  "image_base64": "<base64-encoded image>",
  "top_k": 5
}

→ {
    "predictions": [
      { "scientific_name": "Micropterus salmoides", "common_name": "Largemouth Bass", "confidence": 0.91, "rank": 1 },
      ...
    ],
    "uncertain": false
  }

GET /health  → { "status": "ok", "model_loaded": true }
GET /species → { "species": ["largemouth_bass", ...] }
```

If no trained checkpoint is mounted, the service returns hardcoded stub predictions with `"uncertain": true`.

## Quick Start (standalone)

```bash
# Requires ../omyfish-python/checkpoints/best.pt and ../omyfish-python/data/metadata/fish_info.json
docker compose up

# Service runs on http://localhost:8000
```

## Used by enterprise projects

Both `omyfish-dotnet` and `omyfish-java` docker-compose files reference this directory as their `ai-service` build context:

```yaml
ai-service:
  build:
    context: ../omyfish-ai
    dockerfile: Dockerfile
  volumes:
    - ../omyfish-python/checkpoints:/checkpoints:ro
    - ../omyfish-python/data/metadata:/metadata:ro
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_PATH` | `/checkpoints/best.pt` | Path to the EfficientNet checkpoint |
| `CLASSES_PATH` | `/checkpoints/classes.json` | Path to the class list |
| `METADATA_PATH` | `/metadata/fish_info.json` | Path to species metadata |

## Structure

```
omyfish-ai/
  main.py              FastAPI application
  predictors/
    base.py            Abstract predictor interface
    efficientnet.py    EfficientNet-B3 inference (self-contained, no omyfish-python imports)
    clip.py            CLIP zero-shot fallback
  requirements.txt
  Dockerfile
  docker-compose.yml   Standalone dev stack
```

## Model source

Predictors are derived from `omyfish-python/services/fish_ai/predictors/`. The EfficientNet predictor is kept self-contained (inline model builder + transforms) so this service has no import dependency on the Python repo.
