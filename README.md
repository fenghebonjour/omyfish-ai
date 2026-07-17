---
title: OMyFish AI Service
emoji: 🎣
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 8000
pinned: false
license: mit
---

# omyfish-ai

Standalone AI microservice powering **OMyFish — Your AI Fishing Companion** (*When, Where, What you catch.*), shared by all three OMyFish projects. Two domains:

- **Fish identification** (`/predict`) — species ID from a photo (CLIP gate + EfficientNet-B3).
- **Bite Score** (`/bite-score/*`) — an explainable 0–100 fishing-timing forecast, hourly up to 14 days, tuned per species.

> **HuggingFace Space note:** the YAML header above makes this repo deployable as-is as a Docker
> Space. The Space has no model volumes mounted, so `/predict` runs in stub mode and the CLIP
> gate is skipped — the Bite Score endpoints (what the deployed Streamlit app's Timing tab uses)
> are fully functional without them.

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

### Bite Score

```
GET /bite-score/forecast?lat=37.81&lon=-122.42&species=largemouth_bass&hours=168

→ {
    "species": "largemouth_bass", "lat": 37.81, "lon": -122.42,
    "hourly": [
      { "timestamp": "...", "score": 67.8,
        "breakdown": { "pressure": 78.5, "temperature": 48.7, "wind": 100.0,
                       "water": 37.1, "solunar": 38.8, "sky": 3.0 },
        "weighted_contribution": { ... },
        "time_of_day_multiplier": 1.0, "safety_flag": null },
      ...
    ],
    "best_windows": [ top-3 non-overlapping peak hours ]
  }

GET /bite-score/today?lat=..&lon=..&species=..   → 24h convenience wrapper
GET /bite-score/species-key?name=Micropterus salmoides
→ { "input": "...", "species_key": "largemouth_bass", "matched": true }
```

Every score ships with the full six-factor breakdown — that transparency is a product invariant, never collapse it to a bare number. Storm hours are capped at 15 and carry a `safety_flag` regardless of the other factors. `species` accepts a profile key or a resolvable common/scientific name; `/bite-score/species-key` maps a confirmed fish ID to the key a backend should store for that user's future forecasts.

Data sources (no API keys needed): weather from [Open-Meteo](https://open-meteo.com), tides from NOAA CO-OPS (nearest reference station within 50 km; non-tidal waters fall back to a neutral water factor), solunar computed locally with `ephem`. See `docs/reference/bite_engine/` for the full design rationale.

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
  main.py              FastAPI application (fish-ID endpoints + router assembly)
  predictors/
    base.py            Abstract predictor interface
    efficientnet.py    EfficientNet-B3 inference (self-contained, no omyfish-python imports)
    clip.py            CLIP zero-shot fallback
  bite_prediction/
    engine/            Pure scoring logic — no I/O, unit-testable offline
    providers/         The only I/O boundary (Open-Meteo, NOAA CO-OPS, ephem)
    router.py          FastAPI glue (/bite-score/*)
    schemas.py         Pydantic I/O models
  tests/
    bite_prediction/   pytest suite — runs with zero network access
  docs/reference/
    bite_engine/       Original design spec, kept as "why" documentation
  requirements.txt
  Dockerfile
  docker-compose.yml   Standalone dev stack
```

## Model source

Predictors are derived from `omyfish-python/services/fish_ai/predictors/`. The EfficientNet predictor is kept self-contained (inline model builder + transforms) so this service has no import dependency on the Python repo.
