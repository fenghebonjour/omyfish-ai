# OMyFish AI — Weakness Audit (learning notes)

Ported from `omyfish-dotnet/docs/WEAKNESS_AUDIT.md`'s senior-dev-style review
(2026-09-10) — see that file for the original writeup, and
`omyfish-java`/`omyfish-python-web`'s own `docs/WEAKNESS_AUDIT.md` for how
this translation was already done twice for the enterprise siblings.
Tracked for real work in `BACKLOG.md` item A — this file is the "why",
that file is the "what to do".

**Framing that matters for every entry below:** this service is standalone
and unauthenticated by design — every enterprise sibling's own gateway is
*supposed* to be the thing gating access to it. But per this repo's own
`README.md`, `omyfish-ios` talks to this service directly with no
intermediary gateway at all, and the service is also deployed standalone as
the public Hugging Face Space. So for two of five consumers there is no
upstream gate of any kind — this service's own code is the only thing
between the public internet and both a compute-bound model and a metered
Groq API call.

Confirmed structurally stateless: no DB driver anywhere in `requirements.txt`
or the codebase (`sqlalchemy`/`psycopg`/`sqlite3`/`pymongo`/`redis` all
absent) — model + external-API calls only, no persistence layer. So the
whole "Data layer" tier (§3.1–3.4) is not applicable here, confirmed rather
than assumed.

---

## 1. Security

**Status: fixed and verified 2026-09-11.**

### §1.1 — Gateway configures auth but doesn't enforce it — not applicable

No gateway exists here to desync from its own config. Checked whether *any*
access control exists regardless (API key, header check) — none does. This
is a deliberate design choice, correct for the four backend siblings, but
leaves iOS and the HF Space with nothing between them and `/predict`/
`/regs/ask` — see §1.2, where this actually bites.

### §1.2 — Paid AI endpoints open with no rate limiting — present, fixed

**Problem:** zero rate limiting anywhere. Both the fish-ID model
(`POST /predict`) and the per-call-cost Groq chatbot (`POST /regs/ask`)
were completely open, with two of five consumers (iOS, the public HF
Space) having no upstream gateway to mitigate this at all — the single
most exposed finding in this pass. Compounded by `AskRequest.question`
having no `max_length` (only the LLM's *output* was capped via
`MAX_TOKENS`) and `PredictRequest.image_base64` having no size cap
(uncapped-memory/CPU on top of uncapped-cost).

**Fix:** `rate_limit.py` — a small in-memory per-IP fixed-window limiter
(no Redis, matching `omyfish-java`'s api-gateway `RateLimitFilter` for the
same single-instance reasoning). Applied via `Depends()`:
`/predict` 10/min, `/bite-score/forecast` and `/bite-score/today` 30/min
each (same family-wide rates as the enterprise siblings), `/regs/ask`
10/min (this repo's own call — the siblings never rate-limited their regs
proxies, but this is the only endpoint in the whole family calling a
per-token-billed LLM with no gateway in front of it for two consumers, so
the extra caution is warranted here specifically). Added
`Field(..., max_length=2000)` to `AskRequest.question` and
`Field(..., max_length=15_000_000)` (~11MB decoded) to
`PredictRequest.image_base64`.

**Known limitation:** the in-memory limiter's state is a module-level
singleton, shared for the process lifetime — this matters for the new
route-level tests too (`tests/test_predict_api.py` makes 7 calls to
`/predict` across its test session, currently under the 10/min limit, but
that headroom will shrink if more predict-calling tests are added later).

### §1.3 — Refresh tokens in `localStorage` — not applicable

No user accounts, sessions, or tokens of any kind exist in this service.

### §1.4 — Containers run as root — present, fixed

**Problem:** no `USER` directive in the Dockerfile. Notably, this was the
exact gap `omyfish-java`'s own audit cited when it *excluded* `ai-service`
from its Helm `securityContext` hardening pass — fixing it here unblocks
that already-written sibling fix.

**Fix:** `groupadd`/`useradd` + `USER app`, plus `HF_HOME=/app/.cache/huggingface`
pointed at a directory chowned to the new user — the CLIP fish-gate
downloads its weights via `transformers.CLIPModel.from_pretrained` at first
startup, so the new non-root user needs a writable cache dir, not just a
writable home.

### Model/checkpoint loading — present, fixed

**Problem:** `predictors/efficientnet.py` called `torch.load(...,
weights_only=False)` — full pickle deserialization, capable of arbitrary
code execution if the checkpoint were ever untrusted. Low practical risk
today (first-party checkpoint, read-only mount) but an easy, low-cost fix.

**Fix:** `weights_only=True`. Verified against a real checkpoint
(`omyfish-python/checkpoints/best.pt`, the actual file this predictor
loads in production) before committing to the change — its `config` dict
and `model_state_dict` are entirely within `weights_only=True`'s safe
allowlist (dicts/lists/scalars/tensors).

### `/regs/ask` prompt construction — present, low-severity, not fixed

`llm_client.py` builds the user message via a plain f-string with no
sanitization of `question`. Blast radius is contained by design (single-
hop, no agentic loop, no tool use per this repo's own docs) — a prompt-
injection attempt can at most make the bot go off-brand, not reach other
systems. The concrete risk is cost/abuse via crafted long inputs, which
§1.2's new length cap + rate limit already address. Not fixed separately
in this pass.

---

## 2. Resilience

**Status: §2.2 and the Groq half of §2.1 fixed 2026-09-11. §2.3/§2.4 not
applicable.**

### §2.1 — No timeout/retry/circuit breaker on outbound calls — mixed

- **Weather (Visual Crossing/Open-Meteo) — already fine.** Explicit
  `httpx` timeouts plus a documented retry-with-backoff loop (HF Spaces'
  shared IPs get intermittently throttled). Tide lookups degrade to a
  neutral score on any failure — a deliberate, well-reasoned pattern.
- **Regs zone/limits/consumption clients — timeout present, retry
  absent.** Minor gap, not fixed in this pass (lower urgency — these
  aren't billed per-call like Groq).
- **Groq — fixed.** `llm_client.py::_client()` previously constructed a
  bare `groq.Groq()` with no timeout and no retry — the only outbound call
  site in the service with zero explicit resilience config, on the one
  call that's also the most expensive per-request. Now
  `groq.Groq(timeout=15.0, max_retries=2)`, using the SDK's own built-in
  retry/backoff.
- **No circuit breaker** — consistent with every sibling's own scope
  decision (timeout+retry shipped, no breaker). Not a gap on its own.

### §2.2 — No global exception handling — present, fixed

**Problem:** no `@app.exception_handler` anywhere — an unhandled exception
fell through to Starlette's default. Narrower exposure than in the other
repos, since every router here already does explicit try/except → clean
`HTTPException` for the *known* failure modes; only genuinely unexpected
bugs hit the gap.

**Fix:** `@app.exception_handler(Exception)` in `main.py` — logs and
returns a structured `{"error": "..."}` 500.

### §2.3 / §2.4 — Outbox pattern / consumer idempotency — not applicable

No message broker, no database — nothing here does two related writes
needing atomicity, and nothing consumes redeliverable messages.

---

## 3. Data layer

**Not applicable, tier-wide, confirmed structurally** — see the framing
note at the top of this file. Every response is computed fresh from a
loaded model, a stateless scoring engine, or a live provider call.

---

## 4. Testing/CI

**Status: bite-score route-level tests + CI workflow added 2026-09-11.**

**Problem:** `/predict` and `/regs/*` (including `/ask`) already had good
route-level (`TestClient`) coverage — real Groq/providers properly mocked.
`/bite-score/*` had only engine-level unit tests, no HTTP-layer test for
`GET /bite-score/forecast|today|species-key` — a real, specific gap on the
product's home-screen feature. No CI workflow of any kind existed
(`.github/workflows/` didn't exist) — the existing 84-test suite never ran
anywhere except a developer's own machine.

**Fix:** `tests/bite_prediction/test_router.py` (6 new tests, mirroring
`tests/regs_advisor/test_router.py`'s monkeypatch-the-provider pattern) —
forecast returns scored hours, unknown species → 400, provider-down → 503,
`/today` delegates to `/forecast` with a 24h window, species-key resolution
for both known and unknown names. `.github/workflows/ci.yml` — installs
CPU-only torch (matching the Dockerfile's own reasoning: avoid pulling the
full CUDA wheel stack) then runs `pytest`. 90 tests total, all passing.

---

## Cleanup

No dead-code/scaffold findings. Two near-misses confirmed intentional, not
stale: `docs/reference/bite_engine/` (explicitly labeled "kept as 'why'
documentation" in `README.md`) and `calibration.py`'s unimplemented
`CalibratedWeights` (a documented roadmap item per `CLAUDE.md`, blocked on
real catch-log data).

---

## Bonus findings (not on the dotnet list)

1. **CORS wildcard is correctly scoped, not a bug.** `allow_origins=["*"]`
   with no `allow_credentials=True` — since this service issues no
   cookies and has no session state, a wildcard origin is appropriate
   here, unlike the enterprise gateways' CORS findings (which were
   specifically about combining a wildcard with credentialed requests).
   `docs/CORS_MEMO.md` already documents this tradeoff. Not a finding,
   noted for completeness since every sibling flagged CORS.
2. **`/regs/ask`'s "live limits" enrichment makes an extra, itself-
   unbounded outbound call per request** (`_live_limits_context` in
   `regs_advisor/router.py`) — a second full network round-trip whenever a
   question names both a zone and a species, on top of the Groq call.
   Compounds the §1.2 exposure (now mitigated by the same rate limit/
   length cap, since it's gated behind the same `/ask` endpoint). Not
   fixed separately.
3. **`consumption_client.py` builds an Esri query via manual quote-escaping**
   rather than parameterization, against a public read-only Quebec
   government ArcGIS FeatureServer. Not exploitable today (escaping does
   prevent breaking out of the string literal, target has no write
   capability), but the pattern is worth a comment for whoever touches
   that file next. Not fixed in this pass.
