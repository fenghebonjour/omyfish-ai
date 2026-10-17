# Final report — "live bait allowed in quebec?" fix

See `diagnosis_live_bait.md` for the full Phase 1 write-up. This file covers Phases 2-3
and the overall outcome.

## Diagnosis summary

The original wrong answer ("Yes... commonly used and permitted") was not a retrieval-ranking
or chunking bug. **The KB simply never contained the rule.** Neither `regulations_overview.md`
nor `species_tackle.md` had any passage stating a live-bait-fish rule; every "bait" match was a
species-tackle technique mention. Retrieving at k=10 for 4 phrasings confirmed no chunk holding
the rule existed at any rank. The model filled that gap by inferring permission from technique
descriptions ("live-bait rig... minnow") — a second, confirmed cause.

You supplied the official source
(https://www.quebec.ca/en/tourism-recreation-sport/sporting-and-outdoor-activities/sport-fishing/fishing-techniques/use-baits,
last updated 2026-01-16): live bait fish, regardless of species, have been prohibited
province-wide since 2017-04-01; earthworms/leeches/insects/frogs are not bait fish and remain
permitted; dead bait fish are restricted by species and zone; importing bait fish is prohibited
outright.

## Phases/fixes done vs. skipped

| Item | Status | Why |
|---|---|---|
| Phase 1 diagnosis | Done | `diagnosis_live_bait.md` |
| KB content fix (new "Bait rules" section, `regulations_overview.md`) | Done | Addresses the confirmed primary cause (missing from KB). Verbatim-quoted load-bearing sentences, cited to the source URL + its last-updated date. |
| Fix A (chunking) | **Skipped** | Diagnosis did not confirm chunk-size/dilution as a cause of this failure — no chunk held the rule at any granularity, so splitting chunks differently couldn't have surfaced it. The headingless-intro-chunk issue it would also fix is real but unrelated to this bug. |
| Fix B (glossary) | **Skipped** | Diagnosis did not confirm ranking/vocabulary-gap as the cause — once the KB fix was in place, baseline (unflagged) retrieval already ranked the new "Bait rules" chunk #1 of 4 for all four test phrasings ("live bait allowed in quebec?", "can I use minnows as bait?", "are shiners allowed as bait in Quebec?", "is bait fish legal?"), including the slang terms "shiners"/"minnows" the glossary fix was meant to bridge. See `tests/regs_advisor/test_retrieval.py::test_live_bait_query_ranks_bait_rules_section_first`. |
| Fix C (`REGS_FIX_PINNED`) | Implemented, off by default | `regs_advisor/engine/pinned_rules.py` + `regs_advisor/knowledge_base/pinned_rules.json` (has the required `last_verified` placeholder, **not yet filled in** — needs a human to confirm). Wired into both `router.py` (basic mode) and `engine/agentic.py`. |
| Fix D (`REGS_FIX_GUARDRAIL`) | Implemented, off by default | Addresses the confirmed proximate cause (prompt lets model infer legality from description). Added to both `llm_client.py` and `engine/agentic.py` system prompts; also strips leaked `【...】` citation markers from agentic answers, gated by the same flag. |
| Regression eval items (RB1-RB9) | Done | 9 new items, tier `regression`, in `eval/regs_eval.json`. Original question + 6 casual live-bait variants + 2 Licensing-rule variants (the only other confirmed province-wide rule). No existing item modified. |
| Flag-comparison eval run | **Partially done — Groq daily quota exhausted mid-run** | See below. |
| Phase 3 (web search tool) | **Stopped per your own instruction, not implemented** | See below. |

## ⚠️ Important: existing eval item `W2` encodes the opposite ground truth

Per your answer, `W2` (hard tier, frozen) is left untouched. For the record: `W2`'s own notes
say "no KB passage states a province-wide live-bait ban" and it rewards an answer that live
bait **is** used. That was true of the KB *as it existed before this session*. It is no longer
true of the real-world rule (confirmed via your source) or of the KB after this session's fix.
`W2` still passes under the current code (the model can correctly say the *lures-only* premise
in `W2`'s question is false while *also* being aware live bait fish specifically are banned —
those are different claims), but if you ever want `W2` retired or reworded, that's a decision
for you to make outside this frozen-file constraint; I'm not altering it.

## Flag-comparison results — ⚠️ incomplete, quota-limited, not hidden

I ran `eval/run_fixes_eval.py` (new file, does not touch `run_eval.py`'s frozen graders) across
4 combos — baseline, C, D, C+D — in both basic mode (full eval, n=39) and agentic mode
(regression tier + T3/H2/W1/O1/T2, n=14). **The Groq account's daily token budget (200,000 TPD)
ran out partway through the "C" basic-mode run** (see raw 429 errors in
`eval/results/fixes_comparison.json`/`.md`). Everything after that point in the run — the rest
of "C", all of "D", all of "C+D", and every agentic-mode combo except agentic baseline — came
back as HTTP/API errors, not real model answers. **I am reporting those as "no data," not as
failures** — an API error is not a correctness result, and a table cell that silently showed
"FAIL" for a 429 would misrepresent Fix C/D as broken when they were never actually exercised.

**What I do have clean data for:**

| Combo | Mode | n | Correctness | Note |
|---|---|---|---|---|
| baseline (KB fix only, no flags) | basic | 39 | 35/39 (90%)* | *after correcting one eval-item wording bug found in this run, see below |
| baseline (KB fix only, no flags) | agentic | 14 | 12/14 (86%) | |
| C | basic | 7 of 39 | 6/7 | Only S1-S6 + T3 got real answers before the 429s started; not representative of the full set |
| C, D, C+D | agentic; D, C+D | basic | 0 real | 429 rate-limited, no data |

**The headline finding: the KB content fix alone (no flags at all) already resolves the
original bug and all 9 live-bait regression items, in both basic and agentic mode:**

- Basic mode: RB1-RB9 all pass (9/9) once a substring-matching bug in my own new eval item
  RB5 was fixed — see "Eval item correction" below.
- Agentic mode: RB1-RB9 all pass (9/9), no correction needed.

So for *this specific bug*, Fix C and Fix D were not needed to make the regression suite pass —
the root-cause fix (adding the sourced rule to the KB) was sufficient on its own. Fix D remains
valuable as defense-in-depth against the same *class* of failure recurring for some other
not-yet-documented rule, and Fix C as a backstop if retrieval ever fails to rank a pinned rule
in the top-4 for an unanticipated phrasing — both are implemented, tested (unit tests, no
network needed), off by default, and ready to measure properly once quota resets. I have not
verified empirically that C/D make the regression suite *better or worse* than baseline, and I
am not going to claim that from an unrun (429'd) test.

**Eval item correction (made in this session, item is new/not frozen):** RB2-RB7 originally
required the literal substring "prohibited" (among a few synonyms); one live Groq answer for
RB5 wrote "prohibits" instead ("Québec **prohibits** the possession and use of..."), which is
substantively identical but didn't match. I broadened the synonym lists to include the verb-tense
variants ("prohibits", "bans") — a grading-robustness fix, not a content change. Re-grading the
already-captured RB5 answer (no new Groq call) against the corrected item flips it from FAIL to
PASS.

**Two basic-mode items (`S4`, `T2`) flipped OK→FAIL vs. the pre-existing `baseline_v2.json` —
investigated, not a regression:** both are substring-match false negatives from natural LLM
phrasing variance between runs (Groq sampling is not deterministic), not caused by any change
this session made:
- `S4`: new answer says "6 **fish** in all" where the grader requires the literal substring
  "6 in all" — content is correct, retrieval still hit@3, phrasing just inserted a word.
- `T2`: new answer uses "lake‑sturgeon" with a hyphen where the grader's normalizer expects
  "lake sturgeon" with a space — content is correct, retrieval still hit@3, the model chose to
  hyphenate the compound noun this time.

Everything else that differs from the old `baseline_v2.json`/`agentic_v1.json` (`T3`, `H2`,
`W1`, `O1`) was **already failing identically before this session** — confirmed by diffing
against the pre-existing result files; not a new regression.

## Needs official source (unresolved)

Nothing outstanding from this session — the one gap flagged in Phase 1 (the live-bait ban
text) was resolved by the quebec.ca source you provided. `pinned_rules.json`'s `last_verified`
field is still a placeholder ("REPLACE_ME") — that's intentional per your Fix C spec; please
fill it in once you've confirmed the two pinned rules are current.

## Token usage

This run: **80,035 tokens** (66,445 prompt + 13,590 completion) across **76 Groq calls** before
hitting the account's 200,000-token daily cap (per the 429 payloads, the account was already at
~199,600/200,000 used when my run started — the earlier smoke-test calls plus whatever else ran
on this key today ate most of the budget before the comparison run even began). Quota resets
daily; re-run the comparison after reset (see commands below) to get real numbers for Fix C, D,
and C+D in both modes.

## Exact re-run commands

```bash
cd /home/bigblue/omyfish-ai

# Unit tests (no network, no Groq) — all pass as of this session:
python3 -m pytest tests/ -q

# Retrieval-only sanity check (no LLM, no Groq):
python3 -m pytest tests/regs_advisor/test_retrieval.py tests/regs_advisor/test_pinned_rules.py \
  tests/regs_advisor/test_llm_client.py tests/regs_advisor/test_agentic.py -q

# Original frozen eval runner, unchanged, basic mode, full 39-item set (overwrites baseline_v2.*):
python3 eval/run_eval.py --mode basic

# Original frozen eval runner, unchanged, basic vs agentic compare (overwrites agentic_v1.*):
python3 eval/run_eval.py --mode compare

# New flag-comparison runner (does not touch run_eval.py; writes its own
# eval/results/fixes_comparison.{json,md}; re-run once Groq quota resets for real C/D numbers):
python3 eval/run_fixes_eval.py
```

## Files touched this session

- `regs_advisor/knowledge_base/regulations_overview.md` — added "Bait rules" section (sourced).
- `regs_advisor/knowledge_base/pinned_rules.json` — new, Fix C config + `last_verified` placeholder.
- `regs_advisor/engine/pinned_rules.py` — new, Fix C loader.
- `regs_advisor/providers/llm_client.py` — Fix D guardrail addendum, gated.
- `regs_advisor/engine/agentic.py` — Fix C pinned-rules injection + Fix D guardrail/citation-strip, gated.
- `regs_advisor/router.py` — wires Fix C into the basic-mode `/regs/ask` path.
- `tests/regs_advisor/test_retrieval.py`, `test_router.py` — added tests (existing tests untouched).
- `tests/regs_advisor/test_pinned_rules.py`, `test_llm_client.py`, `test_agentic.py` — new.
- `eval/regs_eval.json` — added 9 `regression`-tier items (RB1-RB9); no existing item modified.
- `eval/run_fixes_eval.py` — new flag-comparison runner; `eval/run_eval.py` untouched.
- `eval/results/diagnosis_live_bait.md`, `eval/results/final_report_live_bait.md` — new.
- Nothing committed (per instructions); nothing in `.env` was read or printed beyond checking
  that `GROQ_API_KEY` is set.
