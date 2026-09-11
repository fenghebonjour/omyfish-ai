# OMyFish AI — Backlog

Deferred ideas and future work. Not committed scope — parking lot for things worth doing.

---

## [x] A — Weakness audit follow-up (ported from omyfish-dotnet)

**Status:** DONE 2026-09-11. `omyfish-dotnet` went through a senior-dev-style
weakness audit (its `BACKLOG.md` item F) covering security, resilience,
data-layer, and testing/CI findings, then asked for the same treatment
across the rest of the family — already ported to `omyfish-java` and
`omyfish-python-web` (their own `BACKLOG.md` item G). Full explanation in
`docs/WEAKNESS_AUDIT.md` — this entry is the "what shipped". This service
is stateless and unauthenticated by design, so the translation looks
different from the enterprise siblings: most of the "Data layer" tier is
not applicable, and §1.2 (rate limiting) is the highest-priority finding
by a wide margin, since two of this service's five consumers (omyfish-ios,
the public Hugging Face Space) call it with no gateway in front of them at
all.

**Security — DONE:**
- ~~No rate limiting on `/predict`/`/regs/ask`~~ — fixed: `rate_limit.py`,
  a small in-memory per-IP fixed-window limiter (no Redis — matches
  `omyfish-java`'s api-gateway choice for a single-instance service).
  `/predict` 10/min, `/bite-score/forecast`+`/today` 30/min each,
  `/regs/ask` 10/min. Also added `max_length` caps on `AskRequest.question`
  (2000 chars) and `PredictRequest.image_base64` (~11MB decoded) — same
  root cause, same fix window. (`WEAKNESS_AUDIT.md` §1.2)
- ~~Containers run as root~~ — fixed: non-root `USER app` in the
  Dockerfile, plus `HF_HOME` pointed at a writable cache dir for the CLIP
  gate's model download. This was the exact gap blocking `omyfish-java`'s
  own Helm hardening pass from covering `ai-service` — fixing it here
  unblocks that already-written sibling fix. (§1.4)
- ~~`torch.load(..., weights_only=False)`~~ — fixed: `weights_only=True`,
  verified against the real production checkpoint before committing.
  (Model/checkpoint loading finding)
- §1.1 (gateway auth) — not applicable, no gateway exists here by design.
- §1.3 (refresh tokens) — not applicable, no user accounts/tokens exist.

**Resilience — DONE (bar circuit breaker, deliberate; bar two lower-priority
retry gaps):**
- ~~Groq client had no timeout/retry~~ — fixed:
  `groq.Groq(timeout=15.0, max_retries=2)`. The only outbound call site in
  the service with zero explicit resilience config, on the call that's
  also the most expensive per-request. (§2.1)
- ~~No global exception handling~~ — fixed: `@app.exception_handler(Exception)`
  in `main.py`. (§2.2)
- §2.3/§2.4 (outbox/idempotency) — not applicable, no broker, no DB.
- Regs zone/limits/consumption clients still have no retry (timeout only)
  — lower urgency than Groq since they're not billed per-call; **not
  fixed**.

**Data layer:** not applicable tier-wide — this service holds no
persistent state.

**Testing/CI — DONE:**
- ~~No route-level test for `/bite-score/*`~~ — fixed:
  `tests/bite_prediction/test_router.py` (6 new tests, mirroring
  `tests/regs_advisor/test_router.py`'s pattern).
- ~~No CI workflow~~ — fixed: `.github/workflows/ci.yml` (installs CPU-only
  torch, runs `pytest`). 90 tests total, all passing.

**Not done in this pass, left for a follow-up round:**
- Retry (not just timeout) on the regs zone/limits/consumption HTTP
  clients.
- `/regs/ask`'s prompt-construction sanitization (low severity, contained
  blast radius per this service's own single-hop-no-tool-use design).
- The Esri query string-escaping pattern in `consumption_client.py` (not
  exploitable today — public read-only dataset, no write capability).
- `_live_limits_context`'s extra unbounded outbound call inside `/regs/ask`
  — now covered by the same rate limit as the endpoint it's nested in, but
  not addressed as its own item.

**Cross-repo note:** this service is bundled wholesale into `omyfish-python`'s
Hugging Face Space Docker image at build time (fetched fresh from GitHub
main — see that repo's `Dockerfile`). No new dependency was added here
(the rate limiter and exception handler use only stdlib + FastAPI/Starlette,
already present), so `omyfish-python`'s bundled `pip install` list needs no
changes for this pass to land cleanly on the Space's next rebuild.
