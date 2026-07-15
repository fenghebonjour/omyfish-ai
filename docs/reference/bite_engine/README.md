# OMyFish Bite Score Engine

Step 3 of the core loop: turning weather/tide data into an explainable
0–100 fishing-timing score, for today and the next 7 days.

## Files

- `species_profiles.py` — per-species weights and temperature comfort
  bands. Edit this file to tune or add species; no code changes needed.
- `bite_score.py` — the actual math. Pure functions, no I/O, fully
  unit-testable. Read this file top to bottom to understand the whole
  model — that's the point.
- `api.py` — FastAPI router (`/bite-score/forecast`, `/bite-score/today`).
  Wire `fetch_hourly_conditions()` to your weather + tide/water-level
  providers; nothing else needs to change.
- `calibration.py` — roadmap only. How hand-tuned weights get replaced
  by weights learned from real catch logs, once the closed beta
  produces enough data, without losing per-factor explainability.
- `smoke_test.py` — runnable example showing a 24h forecast for
  smallmouth bass with a pressure drop mid-morning.

## Why this design

Every competitor markets an "AI forecast" and every competitor's app
reviews call the results unreliable, precisely because none of them
show their work. The whole differentiation here is: **the score always
ships with `breakdown` and `weighted_contribution`** — the mobile app
can (and should) show *why* 6–8am scored 94 and not just the number.

## Integration steps in `omyfish-ai`

1. Drop these files into the FastAPI service alongside the existing
   CV endpoints.
2. Implement `fetch_hourly_conditions()` against your chosen weather
   API (temperature, wind, pressure, cloud/precip) and tide/water-level
   source (NOAA CO-OPS for US tidal waters; a reservoir-level feed or
   simple trend from repeated readings for lakes).
3. Register `router` from `api.py` on the main FastAPI app.
4. Log every forecast shown alongside the eventual catch/no-catch
   outcome from the catch book — this is the dataset `calibration.py`
   describes using later. Start logging on day one even though the
   calibration layer isn't built yet.
5. Add a `species_key` lookup from the existing fish-ID model output
   so the ID and prediction loops connect automatically (identify a
   smallmouth bass today → see a smallmouth-tuned forecast tomorrow).

## Testing

```bash
python3 smoke_test.py
```

No API keys or network access required — the engine is pure math over
a typed `HourlyConditions` struct, so unit tests can construct edge
cases (a sharp pressure crash, a slack tide, a storm flag) directly.
