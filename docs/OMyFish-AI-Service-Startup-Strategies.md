# OMyFish AI Service
Startup Strategies & API Reference
github.com/fenghebonjour/omyfish-ai
Python 3.11  ·  FastAPI  ·  PyTorch  ·  EfficientNet-B3 + CLIP  ·  Standalone microservice

## What It Is
Standalone AI microservice powering OMyFish -- Your AI Fishing Companion (When, Where, What you catch.). Two domains: fish species identification from a photo (POST /predict) and the Bite Score fishing-timing forecast (GET /bite-score/*). Shared by all three OMyFish enterprise and origin projects -- no Python ML dependency lives inside the Java or .NET repos anymore.
### Project family

| Repo | Stack | Role |
| --- | --- | --- |
| omyfish-python | Python 3.11 - PyTorch - FastAPI - Streamlit | AI origin -- HuggingFace Spaces deploy |
| omyfish-dotnet | .NET 10 - ASP.NET Core - EF Core - YARP | .NET enterprise rewrite -- Clean Architecture + CQRS |
| omyfish-java | Java 21 - Spring Boot 3.x - Hibernate - Spring AMQP | Java enterprise rewrite -- Hexagonal + Event-Driven |
| omyfish-ai | Python 3.11 - PyTorch - FastAPI | Shared AI microservice -- used by all three above |

## API Reference

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | /predict | Body: { image_base64, top_k }. Returns top-K species predictions. |
| GET | /health | Returns { status, model_loaded } |
| GET | /species | Returns the full list of supported species keys |
| GET | /bite-score/forecast | Hourly Bite Score forecast (lat, lon, species, hours <= 336) with six-factor breakdown |
| GET | /bite-score/today | 24h convenience wrapper around the forecast |
| GET | /bite-score/species-key | Maps a common/scientific name to a bite-profile species key |

### Request / response shape

> **POST /predict Content-Type: application/json { "image_base64": "<base64-encoded image>", "top_k": 5 } -> 200 OK { "predictions": [ { "scientific_name": "Micropterus salmoides", "common_name": "Largemouth Bass", "confidence": 0.91, "rank": 1 }, ... ], "uncertain": false }**

> **Important -- stub fallback behavior If no trained checkpoint loads successfully at startup, _predictor stays None and every call to /predict returns a hardcoded stub response: Largemouth Bass at confidence 0.42 (rank 1) and Smallmouth Bass at confidence 0.28 (rank 2), with uncertain: true. This is by design -- it lets the service start and respond even with no model -- but it means identical predictions across every uploaded image until checkpoints/best.pt is mounted and loads correctly. Always check GET /health -> model_loaded before trusting prediction accuracy.**

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| MODEL_PATH | /checkpoints/best.pt | Path to the EfficientNet checkpoint |
| CLASSES_PATH | /checkpoints/classes.json | Path to the class list |
| METADATA_PATH | /metadata/fish_info.json | Path to species metadata |
| DISABLE_FISH_ID | (unset) | If set, skips model/fish-gate loading entirely -- bite-score-only mode (used by the omyfish-python HF Space, which bundles this repo) |

> **Bite Score has no env vars and no checkpoint dependency -- its providers (Open-Meteo weather, NOAA CO-OPS tides, local ephem solunar) need no API keys, only outbound internet. The pure engine tests run fully offline: pytest tests/bite_prediction**

## Three Ways to Run This Service

|  | Standalone (uvicorn) | Docker Compose | Consumed by Java/.NET |
| --- | --- | --- | --- |
| Debugger | Full (VS Code / PyCharm) | None (logs only) | Debug the .NET/Java caller; AI service stays a black box |
| Setup effort | Low |  | None -- it's already wired into their docker-compose.yml |
| Checkpoints | Manual env var paths | Volume mount from omyfish-python |  |
| Bite Score | Works -- no checkpoint needed | Works (container needs outbound internet) | Proxied by species-service at /api/v1/species/bite-score/* for the /timing pages |
| Best for | Developing this service itself | Quick smoke test of /predict + /bite-score | Day-to-day Java/.NET development |

## Option 1 -- Standalone with uvicorn (Developing This Service)

> `Best for editing predictors & the bite engine`  ·  `Fast reload`  ·  `Needs sibling omyfish-python`

### Prerequisites
Python 3.11+ -- confirm: python --version
pip
omyfish-python cloned as a sibling directory (for checkpoints and metadata)

### Step-by-step
### Clone alongside omyfish-python

> **cd ~/ git clone https://github.com/fenghebonjour/omyfish-ai git clone https://github.com/fenghebonjour/omyfish-python cd omyfish-ai**

### Install dependencies

> **pip install -r requirements.txt**

### Point env vars at the sibling repo's checkpoints
Set these so main.py finds a real model instead of falling back to stub mode.

> **export MODEL_PATH=../omyfish-python/checkpoints/best.pt export CLASSES_PATH=../omyfish-python/checkpoints/classes.json export METADATA_PATH=../omyfish-python/data/metadata/fish_info.json**

### Run with uvicorn (auto-reload for development)

> **uvicorn main:app --host 0.0.0.0 --port 8000 --reload**

### Verify the model loaded
Check this before testing predictions -- if model_loaded is false, every prediction will be the stub fallback.

> **curl http://localhost:8000/health # -> { "status": "ok", "model_loaded": true }**

### Test a prediction
Base64-encode an image and POST it.

> **python -c "import base64,json; print(json.dumps({ 'image_base64': base64.b64encode(open('fish.jpg','rb').read()).decode(), 'top_k': 5}))" > payload.json curl -X POST http://localhost:8000/predict \ -H 'Content-Type: application/json' \ -d @payload.json**

### Test the Bite Score forecast
Needs no checkpoint or env vars -- only outbound internet for the weather/tide providers. When iterating on the pure scoring logic in bite_prediction/engine/, skip HTTP entirely and run the offline unit tests: pytest tests/bite_prediction

> **curl "http://localhost:8000/bite-score/forecast?lat=37.81&lon=-122.42&species=largemouth_bass&hours=168"**

| Advantages ✓  uvicorn --reload picks up predictor changes instantly ✓  Full Python debugger available (VS Code, PyCharm, pdb) ✓  No Docker required ✓  Fastest loop for editing predictors/efficientnet.py, predictors/clip.py, or the bite_prediction/ domain | Drawbacks ✗  Requires manually exporting 3 env vars every session (or a .env file) ✗  No isolation from your system Python unless you use a venv ✗  Must keep omyfish-python cloned alongside for real checkpoints |
| --- | --- |

> **Best for Actively developing or debugging the predictor logic itself -- tuning confidence thresholds, fixing the species metadata lookup, adding a new model architecture -- or evolving the Bite Score engine (bite_prediction/engine/) with its offline test suite.**

## Option 2 -- Docker Compose Standalone (Quick Smoke Test)

> `One command`  ·  `No debugger`  ·  `Matches enterprise wiring`

### Step-by-step
### Clone both repos as siblings

> **git clone https://github.com/fenghebonjour/omyfish-ai git clone https://github.com/fenghebonjour/omyfish-python cd omyfish-ai**

### Confirm checkpoints exist in omyfish-python
Without these, the container starts in stub mode -- still useful for verifying wiring, but predictions will be the hardcoded fallback.

> **ls ../omyfish-python/checkpoints/best.pt ls ../omyfish-python/data/metadata/fish_info.json**

### Start the service
docker-compose.yml mounts both paths read-only and exposes port 8000.

> **docker compose up # Service runs on http://localhost:8000**

### Verify and test
The bite-score check works even in stub mode (no checkpoint) -- the container only needs outbound internet to reach the weather providers.

> **curl http://localhost:8000/health curl http://localhost:8000/species curl "http://localhost:8000/bite-score/today?lat=37.81&lon=-122.42&species=general"**

### docker-compose.yml volume mounts (standalone dev stack)

> **# Requires ../omyfish-python/checkpoints/best.pt # and ../omyfish-python/data/metadata/fish_info.json services: ai-service: build: . ports: - "8000:8000" volumes: - ../omyfish-python/checkpoints:/checkpoints:ro - ../omyfish-python/data/metadata:/metadata:ro**

| Advantages ✓  Single command -- docker compose up ✓  Reproducible environment matching production ✓  Same image/Dockerfile used when embedded in Java/.NET docker-compose stacks | Drawbacks ✗  No breakpoints -- container logs only ✗  Image rebuild needed after every code change ✗  Requires omyfish-python cloned as a sibling for real checkpoints |
| --- | --- |

> **Best for Quickly verifying the service starts cleanly and /predict + /bite-score/* respond correctly before wiring it into omyfish-java or omyfish-dotnet's docker-compose.yml, or before pointing the omyfish-python Streamlit Timing tab (BITE_SERVICE_URL) at it.**

## Option 3 -- Consumed by omyfish-java / omyfish-dotnet (Normal Day-to-Day Use)

> `Zero setup in this repo`  ·  `Built by the consumer's docker-compose`  ·  `Most common case`

Most of the time you do not run omyfish-ai directly at all. Both omyfish-dotnet and omyfish-java reference this directory as a Docker build context in their own docker-compose.yml, so the AI service is built and started automatically as part of make up in either enterprise repo. Their species-service proxies both domains: POST /predict for fish ID and GET /bite-score/forecast|today for the /timing page in each Next.js frontend.

> **Third consumer -- omyfish-python The Streamlit Timing tab (apps/omyfish_web/timing.py) also consumes this service via BITE_SERVICE_URL (default http://localhost:8000). Locally that means running this repo per Option 1 or 2; the deployed HuggingFace Space instead bundles this repo into its own image from GitHub main (with DISABLE_FISH_ID=1, bite-score-only), so a Space rebuild is what picks up bite-engine changes there.**
### How the consumer wires it in

> **# Inside omyfish-java/docker-compose.yml or omyfish-dotnet/docker-compose.yml ai-service: build: context: ../omyfish-ai dockerfile: Dockerfile volumes: - ../omyfish-python/checkpoints:/checkpoints:ro - ../omyfish-python/data/metadata:/metadata:ro ports: - "8000:8000"**

### Required directory layout

> **omyfish-platform/ omyfish-ai/        <- this repo, referenced as a build context omyfish-python/    <- source of checkpoints/best.pt + fish_info.json omyfish-java/      <- or omyfish-dotnet/, the actual consumer repo you cd into**

### Picking up changes to omyfish-ai while developing the consumer

> **# From inside omyfish-java or omyfish-dotnet: docker compose build ai-service docker compose up -d ai-service**

| Advantages ✓  No setup needed in this repo at all -- the consumer's make up handles it ✓  Identical AI behavior across Java and .NET stacks since both call the same image ✓  Checkpoints and metadata always sourced from the single omyfish-python repo | Drawbacks ✗  A docker compose build ai-service is required in the consumer repo to pick up changes here ✗  Easy to forget the 3-sibling-directory layout requirement when cloning fresh |
| --- | --- |

> **Best for This is the default path for anyone working on omyfish-java or omyfish-dotnet -- no direct interaction with this repo required beyond an initial git clone as a sibling directory.**

## Project Structure

| Path | Contents |
| --- | --- |
| main.py | FastAPI application -- /predict, /health, /species, startup model loading; mounts the bite-score router |
| predictors/base.py | Abstract predictor interface |
| predictors/efficientnet.py | EfficientNet-B3 inference -- self-contained, no omyfish-python imports |
| predictors/clip.py | CLIP zero-shot fallback |
| bite_prediction/router.py + schemas.py | /bite-score/* endpoints -- thin FastAPI glue + the public response contract |
| bite_prediction/engine/ | Pure Bite Score math -- six-factor breakdown, species profiles, no I/O |
| bite_prediction/providers/ | The only I/O boundary -- weather (Open-Meteo), tides (NOAA CO-OPS), solunar (ephem) |
| tests/bite_prediction/ | Engine unit tests -- run offline, no network needed |
| docs/reference/bite_engine/ | Full design rationale for the scoring model |
| requirements.txt | FastAPI, PyTorch, Pillow, pydantic, uvicorn |
| Dockerfile | Container build for standalone or enterprise docker-compose use |
| docker-compose.yml | Standalone dev stack -- mounts ../omyfish-python checkpoints |

> **Model source Predictors are derived from omyfish-python/services/fish_ai/predictors/. The EfficientNet predictor here is kept self-contained -- inline model builder and transforms -- so this service has no import dependency on the Python origin repo at runtime, only a read-only volume mount for the trained weights.**
