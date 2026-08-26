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

Standalone AI microservice powering **OMyFish — Your AI Fishing Companion** (*When, Where, What you catch.*), shared by every enterprise sibling in the family. Three domains:

- **Bite Score** (`/bite-score/*`) — *When*: an explainable 0–100 fishing-timing forecast, hourly up to 14 days, tuned per species.
- **Fish identification** (`/predict`) — *Where*: species ID from a photo (CLIP gate + EfficientNet-B3), paired with GPS-logged observations on a map in the enterprise siblings.
- **Regs & Tips chatbot** (`/regs/*`, newest addition) — *What*: Quebec fishing-regulation lookups plus a free-form Q&A chatbot powered by the Groq API, so anglers know what they can legally keep.

> **HuggingFace Space note:** the YAML header above makes this repo deployable as-is as a Docker
> Space. The Space has no model volumes mounted, so `/predict` runs in stub mode and the CLIP
> gate is skipped — the Bite Score endpoints (what the deployed Streamlit app's Timing tab uses)
> are fully functional without them.

## Project Family

| Repo | Role |
|---|---|
| [omyfish-python](https://github.com/fenghebonjour/omyfish-python) | Python origin — kept in place for training the fish-ID model; Streamlit + FastAPI, deployed on HuggingFace Spaces |
| [omyfish-java](https://github.com/fenghebonjour/omyfish-java) | Java 21 enterprise rewrite — Hexagonal Architecture + Event-Driven |
| [omyfish-dotnet](https://github.com/fenghebonjour/omyfish-dotnet) | .NET 10 enterprise rewrite — Clean Architecture + CQRS |
| [omyfish-python-web](https://github.com/fenghebonjour/omyfish-python-web) | Django monolith (public) — newest enterprise sibling |
| omyfish-ios | SwiftUI native client (private) — newest sibling, talks to this service directly |
| **omyfish-ai** (this) | Shared AI microservice — used by all five above |

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

GET /health  → { "status": "ok", "model_loaded": true, "gate_loaded": true }
GET /species → { "species": ["largemouth_bass", ...] }
```

If no trained checkpoint is mounted, the service returns hardcoded stub predictions with `"uncertain": true`.

If the CLIP fish gate fails to load at startup, the service fails loud rather than silently classifying every image as a fish: `/health` returns `503` with `"status": "degraded", "gate_loaded": false`, and `/predict` returns `503` instead of a prediction. See [docs/troubleshooting.md](docs/troubleshooting.md).

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

Data sources: weather from [OpenWeatherMap](https://openweathermap.org/api/one-call-3) (needs `OPENWEATHERMAP_API_KEY`; hourly data caps the forecast horizon at 48h), tides from NOAA CO-OPS (nearest reference station within 50 km; non-tidal waters fall back to a neutral water factor, no key needed), solunar computed locally with `ephem` (no key needed). See `docs/reference/bite_engine/` for the full design rationale.

### Regs & Tips (newest addition)

Quebec fishing-regulation lookups plus a free-form Q&A chatbot, powered by the [Groq API](https://groq.com):

```
GET  /regs/limits?lat=..&lon=..&species=..        → zone catch/length limits
GET  /regs/zones/geojson                          → all 34 zone polygons, for map overlay
GET  /regs/consumption/stations?lat=..&lon=..      → nearest mercury/consumption sampling sites
GET  /regs/consumption?lat=..&lon=..&species=..    → meals-per-month advisory for a species/size
POST /regs/ask   { "question": "..." }  → { "answer": "...", "sources": [...] }
```

`/regs/ask` does single-hop retrieval-augmented generation: relevant chunks from `regs_advisor/knowledge_base/` are retrieved and passed to Groq (`llama-3.3-70b-versatile` by default, `REGS_CHAT_MODEL` to override) alongside the question in one non-streaming call — no agentic loop. The model is instructed to answer only from the supplied context and to always remind the user to verify current regulations before fishing. Requires a `GROQ_API_KEY` environment variable; see `.env.example`.

## Quick Start (standalone)

```bash
# Requires ../omyfish-python/checkpoints/best.pt and ../omyfish-python/data/metadata/fish_info.json
docker compose up

# Service runs on http://localhost:8000
```

Hit an issue getting it running (stale code after edits, `503`s from `/predict`, etc.)? See
[docs/troubleshooting.md](docs/troubleshooting.md).

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
    providers/         The only I/O boundary (OpenWeatherMap, NOAA CO-OPS, ephem)
    router.py          FastAPI glue (/bite-score/*)
    schemas.py         Pydantic I/O models
  regs_advisor/
    engine/            Zone/limits/consumption parsing, question parsing, retrieval — no I/O
    providers/         Zone/limits/consumption clients + llm_client.py (Groq)
    knowledge_base/    Markdown reference docs used for /ask retrieval
    router.py          FastAPI glue (/regs/*)
    schemas.py         Pydantic I/O models
  tests/
    bite_prediction/   pytest suite — runs with zero network access
    regs_advisor/      pytest suite
  docs/reference/
    bite_engine/       Original design spec, kept as "why" documentation
  requirements.txt
  Dockerfile
  docker-compose.yml   Standalone dev stack
```

## Model source

Predictors are derived from `omyfish-python/services/fish_ai/predictors/`. The EfficientNet predictor is kept self-contained (inline model builder + transforms) so this service has no import dependency on the Python repo.
