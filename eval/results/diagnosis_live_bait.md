# Diagnosis: "live bait allowed in quebec?" wrong answer

Phase 1 only. Read-only — no code or eval items changed to produce this report.

## 1. Every KB passage matching "live bait" / "bait fish" / "minnow" / "bait" (case-insensitive)

Searched both files in `regs_advisor/knowledge_base/`.

**`regulations_overview.md`: zero matches.** This file never mentions bait, minnows,
leeches, or shiners in any form.

**`species_tackle.md`:**

```
13: or live-bait rig (leech, worm, or minnow) along drop-offs and rock humps is
    (full section: "## Walleye (doré jaune)", lines 9-20)

59: fed lakes — and respond to small spinners, wet flies, and live bait fished
    (full section: "## Lake trout (touladi) & brook trout (omble de fontaine)", lines 53-64)

69: than by targeting one fish at a time. Small jigs tipped with a minnow or
    (full section: "## Yellow perch (perchaude) & black crappie (marigane noire)", lines 65-73)

84-85: Sturgeon are bottom feeders, targeted with heavy tackle and bait (worms,
       leeches, or cut bait) fished directly on bottom in deep river channels or
    (full section: "## Lake sturgeon (esturgeon jaune)", lines 82-91)
```

Every one of these is a **technique recommendation** ("X works well," "respond to Y"),
never a legality statement. None says bait fish are permitted or banned, and none
mentions a province-wide rule, a 2017 date, or any possession/use restriction.

**Conclusion for item 1: no passage in either KB file states that live bait fish are
banned, restricted, or legal, province-wide or otherwise.** The claim in the question's
answer ("commonly used and permitted") is not supported by any KB text — it's an
inference the model drew from technique descriptions, not a quote.

## 2. Retriever-only run (TF-IDF, no LLM), top 10, k=10

Ran `regs_advisor.engine.retrieval.get_index().top_k(query, k=10)` directly, no LLM call.

**Query: "live bait allowed in quebec?"**
| rank | score | source | heading |
|---|---|---|---|
| 1 | 0.1421 | species_tackle.md | Lake sturgeon (esturgeon jaune) |
| 2 | 0.1316 | regulations_overview.md | Fishing zones |
| 3 | 0.1113 | species_tackle.md | Walleye (doré jaune) |
| 4 | 0.1032 | regulations_overview.md | *(headingless intro — heading is the raw first line)* |
| 5 | 0.0999 | regulations_overview.md | Licensing |
| 6 | 0.0802 | species_tackle.md | Lake trout & brook trout |
| 7 | 0.0777 | species_tackle.md | Rainbow trout |
| 8 | 0.0538 | species_tackle.md | Yellow perch & black crappie |
| 9 | 0.0481 | species_tackle.md | Atlantic & landlocked salmon |
| 10 | 0.0421 | species_tackle.md | *(headingless intro of species_tackle.md)* |

**Query: "can I use minnows as bait?"** — top 8 (only 8 scored >0), all species_tackle.md
technique sections (sturgeon, rainbow trout, lake/brook trout, walleye, muskellunge) plus
two regulations_overview.md structural sections; none below score 0.15.

**Query: "are shiners allowed as bait in Quebec?"** — top 10, same pattern: species
technique chunks dominate ranks 2-4 and 6-9, "Fishing zones" and "Licensing" interleaved,
plus the headingless intro chunk at rank 10.

**Query: "is bait fish legal?"** — top 10, same pattern, with "Consumption advisories are
a different question" scoring highest (0.2023, driven by shared words "legal"/"fish").

**Conclusion for item 2: across all 4 queries, no chunk containing an explicit live-bait-fish
ban exists at any rank, because no such chunk exists in the corpus at all** (see item 1).
Reporting a rank/score for it is not possible — it's not a retrieval-ranking problem, it's
an absence problem.

## 3. How the (nonexistent) rule would be chunked, if it existed

N/A per item 2 — there's no chunk holding this rule to describe. For context on how
chunking works generally (relevant to Phase 2 Fix A): `retrieval.py:33-46` splits each KB
file on `\n(?=## )`, i.e. one chunk per `##` heading, heading = that line with `## ` stripped.
The text **before** the first `##` heading in each file (the intro paragraph) becomes its
own chunk, but since it has no `## ` prefix, `heading` ends up being that paragraph's raw
first line verbatim — e.g. for `regulations_overview.md` the "heading" is literally
`"This is a plain-language summary to help anglers understand how Quebec fishing"` (cut off
mid-sentence at the line wrap). This headingless chunk appeared in the top 10 for 2 of the 4
queries above (ranks 4 and 10), confirming the user's description of it "crowding" results,
though it is **not** the cause of this specific failure (it doesn't contain bait content
either).

## 4. System prompt and context-assembly code

**Basic mode** (`regs_advisor/providers/llm_client.py:21-29,45-47`): system prompt says
*"Answer using ONLY the reference context provided... If the context doesn't cover the
question, say so plainly"* — this instruction exists but doesn't stop the model from
treating a technique description ("respond to small spinners, wet flies, and live bait")
as evidence that live bait is legal. There is no rule distinguishing *a species description
mentioning an item* from *a rule permitting it*. Context assembly (`router.py:188-199`):
top-4 chunks concatenated with `---` separators, question appended — no per-chunk framing,
no flag for "this chunk is tackle advice, not a legal rule" despite the two KB files having
exactly that distinction (`regulations_overview.md` vs `species_tackle.md`, and
`species_tackle.md`'s own intro line: *"general angling knowledge, not an authoritative
source"*, line 4 — which is in the KB but never surfaced to the model as a framing signal).

**Agentic mode** (`regs_advisor/engine/agentic.py:46-67`): same "answer using ONLY
information returned by search_regs" instruction, plus an existing casual-to-formal
vocabulary rewrite rule (`'minnows'/'shiners' -> 'live bait fish'`, line 54) — i.e. a
glossary-style fix is already partially implemented here for agentic mode only, not basic
mode. Same gap: nothing tells the model a descriptive mention isn't a legal permission.

## 5. Province-wide (all-species, all-zone) passages vs. species/zone-specific ones

| File | Heading | One-line summary | Province-wide basic must-know? |
|---|---|---|---|
| regulations_overview.md | Fishing zones (10-17) | Zones 1-29 exist; limits/seasons/devices are set per zone+species, no single province-wide limit table | Structural fact, not itself a rule |
| regulations_overview.md | What a "limit" usually includes (19-33) | Explains the 4 parts (catch limit, length limit, device, season) a zone entry can have | Structural/meta, not a rule |
| regulations_overview.md | Waterbody-specific exceptions (35-41) | Individual lakes/rivers can have tighter/looser exceptions than the zone table | Structural/meta, not a rule |
| regulations_overview.md | Consumption advisories are a different question (43-52) | Legal to keep ≠ advisable to eat; mercury advisory is separate from catch limit | **Yes** — applies regardless of species/zone |
| regulations_overview.md | Licensing (54-60) | Licence required age 12+, with some free-fishing-day exceptions; non-resident fee differs | **Yes** — the one clear province-wide regulatory rule in the KB |
| regulations_overview.md | Where the numbers in this app come from (62-71) | Data provenance (MFFP, Données Québec), not a rule | Meta, not a rule |
| species_tackle.md | *(all sections)* | Species-by-species tackle/technique advice | Species-specific by definition; file's own intro (line 4) says this is "not an authoritative source" |

**Only one true province-wide regulatory rule exists in the KB: Licensing (age 12+).**
There is no province-wide rule about bait, live bait fish, or any other all-species/all-zone
restriction anywhere in either file.

## 6. Root cause and conclusion

**Root cause ranking:**

1. **Missing from KB (confirmed, primary).** Neither KB file contains any statement that
   live bait fish are banned, restricted, or permitted province-wide. This is not a
   retrieval or chunking problem — item 2 shows the rule isn't retrievable at *any* rank
   because it was never indexed, because it was never written anywhere in the corpus.
2. **Prompt lets the model infer legality from descriptive text (confirmed, proximate
   cause of the specific wrong answer).** Given only technique chunks that *describe* live
   bait as effective for walleye/trout/sturgeon, with no instruction distinguishing
   "mentioned as a technique" from "stated as legal," the model filled the gap by inferring
   permission from description — producing a confident, wrong "Yes... commonly used and
   permitted" instead of "not confirmed in my sources."
3. **Chunk too large/diluted — not confirmed for this failure.** Chunks are already
   per-section and short (~10-13 lines); no evidence dilution hid an existing rule, because
   no chunk holds that rule to dilute.
4. **Outranked by species chunks — not confirmed as the root cause, but a related
   contributing factor.** Species chunks *do* dominate top ranks (items 2 above) purely on
   keyword overlap with "bait"/"minnow", and are what's cited in the model's wrong answer —
   but since no chunk anywhere contains the actual rule, no re-ranking would have surfaced
   it. This is secondary, not causal.

**Smallest fix per confirmed cause, ranked:**

1. For cause 1 (missing from KB): **cannot be fixed by this session** without an official
   source. Per the global rule against writing regulation facts from the model's own
   knowledge, the actual ban text and its citation must come from you. → listed under
   "needs official source" below.
2. For cause 2 (prompt inference): **Fix D (guardrail)** is the smallest and most direct
   fix — it doesn't require new KB content, it changes the failure mode from "confident
   wrong answer" to "not confirmed in my sources, check quebec.ca," which is correct/safe
   behavior even with the KB gap unresolved.
3. Fixes A (chunking) and B (glossary) target causes 3 and 4, which this diagnosis did
   **not** confirm as root causes of this specific failure — they're legitimate general
   retrieval-quality improvements, but won't fix this question on their own since the
   target rule isn't in the corpus at any chunking granularity or rank.
4. Fix C (pinned core rules) can proceed for the **one confirmed province-wide rule** found
   in item 5 (Licensing, age 12+) using KB text verbatim. It **cannot** include a live-bait
   rule — there is nothing in the sources to pin.

**⚠️ Important conflict found, not something this session can resolve on its own:**
The existing eval item `W2` (tier: hard, category: `premise_check`,
`eval/regs_eval.json`) was written with the explicit premise that there is **no**
province-wide live-bait ban — its `notes` field says *"False/unsupported premise: no KB
passage states a province-wide live-bait ban; several species sections recommend live
bait"* and its `expected_facts` (`live bait`, `minnow`, `leech`, `worm`, `match_mode: any`)
currently reward an answer that says live bait **is** used/allowed. If the real-world rule
is in fact a province-wide ban (per your source material, effective 2017-04-01), then `W2`
encodes the opposite of the true legal answer as "correct" — but per the global rule
("do NOT modify ... any existing eval item"), this diagnosis leaves `W2` untouched and
flags it here instead of changing it. This needs your input before Phase 2 can safely add
regression items or a pinned rule for this topic, otherwise the new regression items and
`W2` will assert contradictory ground truth about the same regulation.

## Needs official source

- The claim "use or possession of live bait fish is strictly banned province-wide (since
  April 1, 2017)" — not present in `regulations_overview.md` or `species_tackle.md` in any
  form. Needed: the actual regulation text/citation (quebec.ca or legisquebec.gouv.qc.ca)
  so it can be added to the KB with a proper source line, and so `W2`'s contradiction above
  can be resolved (e.g. by adding a new, correctly-sourced regression item rather than
  editing the frozen `W2`).

## Phases/fixes being skipped (pending your input) and why

- **Fix A (chunking)** and **Fix B (glossary)**: not skipped outright, but diagnosis didn't
  confirm them as root causes for *this* question — see ranking above. Can still implement
  as general quality fixes if you want them, per your Phase 2 instructions, but they won't
  change the live-bait answer's correctness on their own.
- **Fix C (pinned core rules)**: proceeding only for the Licensing rule (the one confirmed
  province-wide rule in the KB). Not adding anything about live bait until you supply a
  source.
- **New regression eval items about live bait**: holding off on writing these until the
  `W2` conflict above is resolved one way or the other, so the regression tier doesn't
  contradict the existing eval suite's ground truth.
