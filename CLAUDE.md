# OMyFish AI Service — context for Claude Code

## Domains in this service
- `predictors/` + the fish-ID endpoints in `main.py` — fish species ID (CLIP gate + EfficientNet-B3). Existing, don't touch without being asked.
- `bite_prediction/` — fishing-timing "Bite Score" engine. See `bite_prediction/engine/` for the pure scoring logic and `docs/reference/bite_engine/README.md` for full design rationale.

## Structure convention (apply to any new domain)
Each feature domain gets the same three-part shape:
- `engine/` — pure logic, no I/O, fully unit-testable without network access.
- `providers/` — the only I/O boundary (external APIs); swappable without touching `engine/`.
- `router.py` + `schemas.py` — thin FastAPI glue; no business logic here.

`main.py` assembles routers from each domain — new domains must not add logic there (the fish-ID endpoints predate this convention).

## Why the bite-score breakdown matters (product context)
The bite-score's per-factor transparency (`breakdown`, `weighted_contribution`) is a deliberate
product differentiator, not incidental detail: competitors' "AI forecasts" are opaque and their
own app reviews call the results unreliable. Never collapse the six-factor breakdown into a
single opaque number anywhere in the pipeline — the mobile client is expected to display it.

## Safety-relevant logic
Storm conditions must suppress the *headline* score (currently capped at 15), not just one
sub-factor — a strong pressure/wind/temperature reading should never be able to outweigh an
active storm flag into a high number. Any change to the weighting/aggregation logic must
preserve this invariant; add a test for it if you touch `compute_bite_score`.

## Out of scope until further notice
- No ML/sklearn dependency for scoring — `calibration.py` is a documented roadmap, not something
  to implement yet. It requires real catch-log data from a closed beta first.
- Providers are chosen and wired (2026-07-15): Open-Meteo for weather, NOAA CO-OPS for tides,
  local `ephem` for solunar. Don't swap a provider unilaterally — ask first.
