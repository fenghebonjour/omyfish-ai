"""
run_eval.py — baseline eval runner for the Regs & Tips chatbot (/regs/ask).

Calls the retrieval index and the router's ask() function directly (in-process,
no HTTP server needed) against regs_eval.json, and scores two things per
question:
  1. retrieval hit@3 — does EVERY chunk in the item's source_chunks appear in
     the top-3 TF-IDF results from regs_advisor.engine.retrieval.get_index()?
     (basic-tier items list one chunk; hard-tier items can list several, all
     of which must be retrieved for the item to pass.)
  2. answer correctness — by default, do ALL expected_facts appear in the
     final answer (case-insensitive substring match)? Two item flags change
     this:
       - "out_of_scope": true — pass only if the answer looks like a
         decline/"don't know" instead of matching expected_facts.
       - "match_mode": "any" — pass if AT LEAST ONE expected_facts string
         appears, instead of requiring all of them. Used for the hard-tier
         premise_check/vague items, where "expected_facts" is really a list
         of acceptable correction/clarification phrasings — a heuristic,
         not an exhaustive list (see the report for this limitation).

Reports are broken down by category, by tier (basic/hard), and separately
for items tagged "vocab_gap": true (hard-tier items phrased in an angler's
casual words rather than the KB's own terms).

Does not modify any regs_advisor/ pipeline code. Reads GROQ_API_KEY from the
environment (via .env if present, never hardcoded).

Usage:
    cd /home/bigblue/omyfish-ai && python3 eval/run_eval.py
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from regs_advisor.engine.retrieval import get_index  # noqa: E402
from regs_advisor.providers.llm_client import LLMError  # noqa: E402
from regs_advisor.router import ask as router_ask  # noqa: E402
from regs_advisor.schemas import AskRequest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

EVAL_PATH = Path(__file__).parent / "regs_eval.json"
RESULTS_DIR = Path(__file__).parent / "results"

DECLINE_PHRASES = [
    "don't know", "do not know", "not available", "cannot provide", "can't provide",
    "no information", "not in my reference", "doesn't cover", "not covered",
    "check quebec.ca", "not sure", "unable to find", "no data", "not provided",
    "i don't have", "not specified", "can't find", "couldn't find", "not mentioned",
    "doesn't include", "does not include", "doesn't specify", "does not specify",
    "doesn't say", "does not say", "does not specify whether", "not specify whether",
]

# Normalize Unicode hyphen/dash variants (U+2010 hyphen, U+2011 non-breaking
# hyphen, U+2012 figure dash, U+2013 en dash, U+2014 em dash) to ASCII "-" so
# an LLM-rendered "angling‑only" still matches the literal "angling-only" fact.
_DASH_CHARS = "‐‑‒–—"
_APOSTROPHE_CHARS = "‘’"
# Unicode space variants an LLM may render (NBSP, narrow no-break space, thin
# space, etc.) that look identical to a regular space but break substring
# matching otherwise.
_SPACE_CHARS = "              "


def _normalize(text: str) -> str:
    for ch in _DASH_CHARS:
        text = text.replace(ch, "-")
    for ch in _APOSTROPHE_CHARS:
        text = text.replace(ch, "'")
    for ch in _SPACE_CHARS:
        text = text.replace(ch, " ")
    return text.lower()


def looks_like_decline(answer: str) -> bool:
    a = _normalize(answer)
    return any(phrase in a for phrase in DECLINE_PHRASES)


def retrieval_hit_at_3(question: str, expected_chunks: list[dict]) -> dict:
    if not expected_chunks:
        return {"applicable": False, "passed": None, "retrieved": []}
    top3 = get_index().top_k(question, k=3)
    retrieved = [{"file": c.source, "heading": c.heading, "score": round(score, 4)} for c, score in top3]
    retrieved_set = {(r["file"], r["heading"]) for r in retrieved}
    expected_set = {(c["file"], c["heading"]) for c in expected_chunks}
    passed = expected_set.issubset(retrieved_set)
    return {"applicable": True, "passed": passed, "retrieved": retrieved}


def answer_correctness(answer: str, item: dict) -> dict:
    if item["out_of_scope"]:
        passed = looks_like_decline(answer)
        return {"passed": passed, "missing_facts": [] if passed else ["<decline/unknown phrasing>"]}

    a = _normalize(answer)
    present = [f for f in item["expected_facts"] if _normalize(f) in a]
    missing = [f for f in item["expected_facts"] if f not in present]

    if item.get("match_mode") == "any":
        passed = len(present) > 0
        # A "vague" question's correct behavior is either to explicitly ask for/
        # state the missing detail (one of the item's expected_facts phrasings)
        # OR to decline to guess without it — both count as handling the
        # ambiguity correctly, so fall back to the same decline-phrase check
        # used for out_of_scope items.
        if not passed and item.get("category") == "vague":
            passed = looks_like_decline(answer)
        return {"passed": passed, "missing_facts": [] if passed else list(item["expected_facts"])}

    return {"passed": not missing, "missing_facts": missing}


async def run_one(item: dict) -> dict:
    retrieval = retrieval_hit_at_3(item["question"], item["source_chunks"])
    try:
        response = await router_ask(AskRequest(question=item["question"]))
        answer, sources, error = response.answer, response.sources, None
    except HTTPException as e:
        answer, sources, error = "", [], f"HTTP {e.status_code}: {e.detail}"
    except LLMError as e:
        answer, sources, error = "", [], f"LLMError: {e}"

    correctness = answer_correctness(answer, item) if error is None else {"passed": False, "missing_facts": ["<error>"]}

    return {
        "id": item["id"],
        "tier": item["tier"],
        "category": item["category"],
        "vocab_gap": item.get("vocab_gap", False),
        "question": item["question"],
        "answer": answer,
        "sources_returned": sources,
        "error": error,
        "retrieval": retrieval,
        "correctness": correctness,
    }


def _bucket_stats(results: list[dict]) -> dict:
    retrieval_applicable = [r for r in results if r["retrieval"]["applicable"]]
    hit3 = (
        sum(1 for r in retrieval_applicable if r["retrieval"]["passed"]) / len(retrieval_applicable)
        if retrieval_applicable else None
    )
    correctness = sum(1 for r in results if r["correctness"]["passed"]) / len(results) if results else None
    return {
        "n": len(results),
        "hit_at_3": hit3,
        "hit_at_3_fraction": f"{sum(1 for r in retrieval_applicable if r['retrieval']['passed'])}/{len(retrieval_applicable)}" if retrieval_applicable else "n/a",
        "correctness": correctness,
        "correctness_fraction": f"{sum(1 for r in results if r['correctness']['passed'])}/{len(results)}" if results else "n/a",
    }


def summarize(results: list[dict]) -> dict:
    by_category: dict[str, dict] = {}
    by_tier: dict[str, dict] = {}

    for r in results:
        by_category.setdefault(r["category"], []).append(r)
        by_tier.setdefault(r["tier"], []).append(r)

    vocab_gap_results = [r for r in results if r["vocab_gap"]]

    return {
        "overall": _bucket_stats(results),
        "by_tier": {tier: _bucket_stats(rs) for tier, rs in by_tier.items()},
        "by_category": {cat: _bucket_stats(rs) for cat, rs in by_category.items()},
        "vocab_gap": _bucket_stats(vocab_gap_results) if vocab_gap_results else None,
    }


def _fmt_pct(stats: dict) -> tuple[str, str]:
    hit3 = f"{stats['hit_at_3']:.0%} ({stats['hit_at_3_fraction']})" if stats["hit_at_3"] is not None else "n/a"
    correctness = f"{stats['correctness']:.0%} ({stats['correctness_fraction']})" if stats["correctness"] is not None else "n/a"
    return hit3, correctness


def write_markdown(results: list[dict], summary: dict, out_path: Path) -> None:
    lines = ["# Regs & Tips chatbot — baseline eval v2 (basic + hard tiers)", ""]
    hit3, correctness = _fmt_pct(summary["overall"])
    lines.append(f"- Overall hit@3: {hit3}")
    lines.append(f"- Overall answer correctness: {correctness}")
    lines.append("")

    lines.append("## By tier")
    lines.append("")
    lines.append("| tier | n | hit@3 | correctness |")
    lines.append("|---|---|---|---|")
    for tier, stats in summary["by_tier"].items():
        hit3, correctness = _fmt_pct(stats)
        lines.append(f"| {tier} | {stats['n']} | {hit3} | {correctness} |")
    lines.append("")

    lines.append("## By category")
    lines.append("")
    lines.append("| category | n | hit@3 | correctness |")
    lines.append("|---|---|---|---|")
    for cat, stats in summary["by_category"].items():
        hit3, correctness = _fmt_pct(stats)
        lines.append(f"| {cat} | {stats['n']} | {hit3} | {correctness} |")
    lines.append("")

    if summary["vocab_gap"]:
        lines.append("## vocab_gap items only (casual phrasing, differs from KB wording)")
        lines.append("")
        hit3, correctness = _fmt_pct(summary["vocab_gap"])
        lines.append(f"- n={summary['vocab_gap']['n']}, hit@3: {hit3}, correctness: {correctness}")
        lines.append("")

    lines.append("## Failures")
    lines.append("")
    any_failure = False
    for r in results:
        failed_retrieval = r["retrieval"]["applicable"] and not r["retrieval"]["passed"]
        failed_correctness = not r["correctness"]["passed"]
        if not (failed_retrieval or failed_correctness):
            continue
        any_failure = True
        gap = " vocab_gap" if r["vocab_gap"] else ""
        lines.append(f"### {r['id']} [{r['tier']}{gap}] ({r['category']})")
        lines.append(f"- Question: {r['question']}")
        if r["error"]:
            lines.append(f"- Error: {r['error']}")
        else:
            lines.append(f"- Answer: {r['answer']}")
        if failed_retrieval:
            lines.append(f"- Retrieval miss — retrieved: {[ (c['file'], c['heading']) for c in r['retrieval']['retrieved']]}")
        if failed_correctness:
            lines.append(f"- Correctness miss — missing facts: {r['correctness']['missing_facts']}")
        lines.append("")
    if not any_failure:
        lines.append("None.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    eval_data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    results = []
    for item in eval_data["items"]:
        result = await run_one(item)
        results.append(result)
        tag = "OK" if result["correctness"]["passed"] else "FAIL"
        gap = " vocab_gap" if result["vocab_gap"] else ""
        print(f"[{tag}] {result['id']} [{result['tier']}{gap}] ({result['category']}): {result['question'][:60]}")

    summary = summarize(results)

    print()
    hit3, correctness = _fmt_pct(summary["overall"])
    print(f"Overall hit@3: {hit3}")
    print(f"Overall answer correctness: {correctness}")

    print()
    print("By tier:")
    for tier, stats in summary["by_tier"].items():
        hit3, correctness = _fmt_pct(stats)
        print(f"  {tier:8s} n={stats['n']}  hit@3={hit3}  correctness={correctness}")

    print()
    print("By category:")
    for cat, stats in summary["by_category"].items():
        hit3, correctness = _fmt_pct(stats)
        print(f"  {cat:15s} n={stats['n']}  hit@3={hit3}  correctness={correctness}")

    if summary["vocab_gap"]:
        hit3, correctness = _fmt_pct(summary["vocab_gap"])
        print()
        print(f"vocab_gap items: n={summary['vocab_gap']['n']}  hit@3={hit3}  correctness={correctness}")

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "baseline_v2.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_markdown(results, summary, RESULTS_DIR / "baseline_v2.md")
    print(f"\nSaved {RESULTS_DIR / 'baseline_v2.json'} and {RESULTS_DIR / 'baseline_v2.md'}")


# ─────────────────────────────────────────────────────────────────────────
# Agentic mode (REGS_MODE=agentic) — everything below is new/additive for
# the basic-vs-agentic comparison. It calls the SAME frozen
# retrieval_hit_at_3 / answer_correctness / summarize functions above
# unmodified; it does not alter their logic or how basic-tier/existing
# items are defined or scored.
# ─────────────────────────────────────────────────────────────────────────

async def run_one_basic_timed(item: dict) -> dict:
    """Identical to run_one(), plus a wall-clock timer, for a fair basic-vs-
    agentic latency comparison run in the same session. Does not change
    run_one() or its grading."""
    t0 = time.monotonic()
    result = await run_one(item)
    result["tool_call_count"] = 0
    result["queries"] = []
    result["latency_seconds"] = round(time.monotonic() - t0, 3)
    return result


def retrieval_hit_at_3_agentic(expected_chunks: list[dict], retrieved_chunks: list[dict]) -> dict:
    """Agentic-mode retrieval scoring, as specified for this comparison: hit@3
    is redefined as 'all required chunks appear among the UNION of chunks
    retrieved across every search_regs call for this question' -- agentic
    mode can retrieve up to 3 x 3 = 9 chunks total, not a single top-3 pass,
    so this number is NOT directly comparable to single-hop hit@3 (noted
    again in the markdown report)."""
    if not expected_chunks:
        return {"applicable": False, "passed": None, "retrieved": retrieved_chunks}
    retrieved_set = {(c["file"], c["heading"]) for c in retrieved_chunks}
    expected_set = {(c["file"], c["heading"]) for c in expected_chunks}
    passed = expected_set.issubset(retrieved_set)
    return {"applicable": True, "passed": passed, "retrieved": retrieved_chunks}


async def run_one_agentic(item: dict) -> dict:
    t0 = time.monotonic()
    try:
        response = await router_ask(AskRequest(question=item["question"]))
        answer, sources, error = response.answer, response.sources, None
        tool_call_count = response.tool_call_count or 0
        queries = response.queries or []
    except HTTPException as e:
        answer, sources, error = "", [], f"HTTP {e.status_code}: {e.detail}"
        tool_call_count, queries = 0, []
    except LLMError as e:
        answer, sources, error = "", [], f"LLMError: {e}"
        tool_call_count, queries = 0, []
    latency = round(time.monotonic() - t0, 3)

    retrieved_pairs: set[tuple[str, str]] = set()
    for q in queries:
        for rid in q.get("result_ids", []):
            file, _, heading = rid.partition("#")
            retrieved_pairs.add((file, heading))
    retrieved_chunks = [{"file": f, "heading": h} for f, h in retrieved_pairs]

    retrieval = retrieval_hit_at_3_agentic(item["source_chunks"], retrieved_chunks)
    correctness = answer_correctness(answer, item) if error is None else {"passed": False, "missing_facts": ["<error>"]}

    return {
        "id": item["id"],
        "tier": item["tier"],
        "category": item["category"],
        "vocab_gap": item.get("vocab_gap", False),
        "question": item["question"],
        "answer": answer,
        "sources_returned": sources,
        "error": error,
        "retrieval": retrieval,
        "correctness": correctness,
        "tool_call_count": tool_call_count,
        "queries": queries,
        "latency_seconds": latency,
    }


def write_markdown_agentic(
    basic_results: list[dict], agentic_results: list[dict],
    basic_summary: dict, agentic_summary: dict, changed: list[dict],
    out_path: Path,
) -> None:
    lines = ["# Regs & Tips chatbot — basic vs agentic retrieval (v1)", ""]
    lines.append(
        "Agentic hit@3 is scored against the UNION of chunks retrieved across all "
        "search_regs calls for a question (up to 3 calls x top-3 each = up to 9 chunks), "
        "not a single top-3 pass like basic mode -- the two hit@3 numbers below are "
        "not directly comparable; they're reported side by side for visibility, not parity."
    )
    lines.append("")

    avg_tool_calls = sum(r["tool_call_count"] for r in agentic_results) / len(agentic_results)
    avg_latency_agentic = sum(r["latency_seconds"] for r in agentic_results) / len(agentic_results)
    avg_latency_basic = sum(r["latency_seconds"] for r in basic_results) / len(basic_results)
    lines.append(f"- Average tool calls per question (agentic): {avg_tool_calls:.2f}")
    lines.append(f"- Average latency per question: basic {avg_latency_basic:.2f}s, agentic {avg_latency_agentic:.2f}s")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append("| mode | n | hit@3 | correctness |")
    lines.append("|---|---|---|---|")
    for label, summary in [("basic", basic_summary), ("agentic", agentic_summary)]:
        hit3, correctness = _fmt_pct(summary["overall"])
        lines.append(f"| {label} | {summary['overall']['n']} | {hit3} | {correctness} |")
    lines.append("")

    lines.append("## By tier")
    lines.append("")
    lines.append("| tier | basic hit@3 | agentic hit@3 | basic correctness | agentic correctness |")
    lines.append("|---|---|---|---|---|")
    for tier in basic_summary["by_tier"]:
        bh, bc = _fmt_pct(basic_summary["by_tier"][tier])
        ah, ac = _fmt_pct(agentic_summary["by_tier"].get(tier, basic_summary["by_tier"][tier]))
        lines.append(f"| {tier} | {bh} | {ah} | {bc} | {ac} |")
    lines.append("")

    lines.append("## By category")
    lines.append("")
    lines.append("| category | basic hit@3 | agentic hit@3 | basic correctness | agentic correctness |")
    lines.append("|---|---|---|---|---|")
    for cat in basic_summary["by_category"]:
        bh, bc = _fmt_pct(basic_summary["by_category"][cat])
        ah, ac = _fmt_pct(agentic_summary["by_category"].get(cat, basic_summary["by_category"][cat]))
        lines.append(f"| {cat} | {bh} | {ah} | {bc} | {ac} |")
    lines.append("")

    if basic_summary["vocab_gap"] and agentic_summary["vocab_gap"]:
        lines.append("## vocab_gap items only")
        lines.append("")
        bh, bc = _fmt_pct(basic_summary["vocab_gap"])
        ah, ac = _fmt_pct(agentic_summary["vocab_gap"])
        lines.append(f"- n={basic_summary['vocab_gap']['n']}")
        lines.append(f"- basic:   hit@3 {bh}, correctness {bc}")
        lines.append(f"- agentic: hit@3 {ah}, correctness {ac}")
        lines.append("")

    lines.append("## Questions whose correctness result changed (basic -> agentic)")
    lines.append("")
    if not changed:
        lines.append("None.")
    else:
        for c in changed:
            arrow = "FAIL -> OK" if (not c["basic_passed"] and c["agentic_passed"]) else "OK -> FAIL"
            lines.append(f"- **{c['id']}** [{c['tier']}] ({c['category']}) {arrow}: {c['question']}")
    lines.append("")

    lines.append("## Agentic per-question log")
    lines.append("")
    for r in agentic_results:
        lines.append(f"### {r['id']} ({r['category']}) — {r['tool_call_count']} tool call(s), {r['latency_seconds']}s")
        lines.append(f"- Question: {r['question']}")
        for q in r["queries"]:
            lines.append(f"  - search_regs(query={q['query']!r}, species={q['species']!r}, zone={q['zone']!r}) -> {q['result_ids']}")
        if r["error"]:
            lines.append(f"- Error: {r['error']}")
        else:
            lines.append(f"- Answer: {r['answer']}")
        lines.append(f"- Retrieval (union) passed: {r['retrieval']['passed']}")
        lines.append(f"- Correctness passed: {r['correctness']['passed']}" + (f" — missing: {r['correctness']['missing_facts']}" if not r["correctness"]["passed"] else ""))
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main_compare() -> None:
    eval_data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    items = eval_data["items"]

    os.environ.pop("REGS_MODE", None)
    print("=== basic (single-hop) ===")
    basic_results = []
    for item in items:
        r = await run_one_basic_timed(item)
        basic_results.append(r)
        tag = "OK" if r["correctness"]["passed"] else "FAIL"
        print(f"[{tag}] {r['id']}  {r['latency_seconds']}s")

    os.environ["REGS_MODE"] = "agentic"
    print()
    print("=== agentic ===")
    agentic_results = []
    for item in items:
        r = await run_one_agentic(item)
        agentic_results.append(r)
        tag = "OK" if r["correctness"]["passed"] else "FAIL"
        print(f"[{tag}] {r['id']}  tool_calls={r['tool_call_count']}  {r['latency_seconds']}s")
    os.environ.pop("REGS_MODE", None)

    basic_summary = summarize(basic_results)
    agentic_summary = summarize(agentic_results)

    by_id_basic = {r["id"]: r for r in basic_results}
    changed = []
    for ar in agentic_results:
        br = by_id_basic.get(ar["id"])
        if br and br["correctness"]["passed"] != ar["correctness"]["passed"]:
            changed.append({
                "id": ar["id"], "tier": ar["tier"], "category": ar["category"],
                "basic_passed": br["correctness"]["passed"], "agentic_passed": ar["correctness"]["passed"],
                "question": ar["question"],
            })

    print()
    hit3, correctness = _fmt_pct(basic_summary["overall"])
    print(f"Basic    overall: hit@3={hit3}  correctness={correctness}")
    hit3, correctness = _fmt_pct(agentic_summary["overall"])
    print(f"Agentic  overall: hit@3={hit3}  correctness={correctness} (union-of-calls hit@3, not comparable 1:1)")
    avg_tool_calls = sum(r["tool_call_count"] for r in agentic_results) / len(agentic_results)
    avg_latency_agentic = sum(r["latency_seconds"] for r in agentic_results) / len(agentic_results)
    avg_latency_basic = sum(r["latency_seconds"] for r in basic_results) / len(basic_results)
    print(f"Avg tool calls (agentic): {avg_tool_calls:.2f}")
    print(f"Avg latency: basic={avg_latency_basic:.2f}s  agentic={avg_latency_agentic:.2f}s")
    print(f"Questions whose correctness result changed: {len(changed)}")
    for c in changed:
        arrow = "FAIL -> OK" if (not c["basic_passed"] and c["agentic_passed"]) else "OK -> FAIL"
        print(f"  {c['id']}: {arrow}")

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "agentic_v1.json").write_text(
        json.dumps(
            {
                "basic_summary": basic_summary,
                "agentic_summary": agentic_summary,
                "avg_tool_calls_agentic": avg_tool_calls,
                "avg_latency_seconds_basic": avg_latency_basic,
                "avg_latency_seconds_agentic": avg_latency_agentic,
                "changed": changed,
                "basic_results": basic_results,
                "agentic_results": agentic_results,
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_markdown_agentic(basic_results, agentic_results, basic_summary, agentic_summary, changed, RESULTS_DIR / "agentic_v1.md")
    print(f"\nSaved {RESULTS_DIR / 'agentic_v1.json'} and {RESULTS_DIR / 'agentic_v1.md'}")


async def main_retry_agentic(ids: list[str]) -> None:
    """Re-run only the given item ids in agentic mode and merge the fresh
    results into the existing eval/results/agentic_v1.json -- for recovering
    from a mid-run Groq rate-limit (429) without re-spending quota on the
    items that already completed cleanly, or re-running basic mode again."""
    existing = json.loads((RESULTS_DIR / "agentic_v1.json").read_text(encoding="utf-8"))
    eval_data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    items_by_id = {it["id"]: it for it in eval_data["items"]}

    os.environ["REGS_MODE"] = "agentic"
    fresh_by_id = {}
    for item_id in ids:
        item = items_by_id[item_id]
        r = await run_one_agentic(item)
        fresh_by_id[item_id] = r
        tag = "OK" if r["correctness"]["passed"] else "FAIL"
        print(f"[{tag}] {r['id']}  tool_calls={r['tool_call_count']}  {r['latency_seconds']}s  error={r['error']}")
    os.environ.pop("REGS_MODE", None)

    agentic_results = [fresh_by_id.get(r["id"], r) for r in existing["agentic_results"]]
    basic_results = existing["basic_results"]

    basic_summary = summarize(basic_results)
    agentic_summary = summarize(agentic_results)

    by_id_basic = {r["id"]: r for r in basic_results}
    changed = []
    for ar in agentic_results:
        br = by_id_basic.get(ar["id"])
        if br and br["correctness"]["passed"] != ar["correctness"]["passed"]:
            changed.append({
                "id": ar["id"], "tier": ar["tier"], "category": ar["category"],
                "basic_passed": br["correctness"]["passed"], "agentic_passed": ar["correctness"]["passed"],
                "question": ar["question"],
            })

    avg_tool_calls = sum(r["tool_call_count"] for r in agentic_results) / len(agentic_results)
    avg_latency_agentic = sum(r["latency_seconds"] for r in agentic_results) / len(agentic_results)
    avg_latency_basic = sum(r["latency_seconds"] for r in basic_results) / len(basic_results)

    (RESULTS_DIR / "agentic_v1.json").write_text(
        json.dumps(
            {
                "basic_summary": basic_summary,
                "agentic_summary": agentic_summary,
                "avg_tool_calls_agentic": avg_tool_calls,
                "avg_latency_seconds_basic": avg_latency_basic,
                "avg_latency_seconds_agentic": avg_latency_agentic,
                "changed": changed,
                "basic_results": basic_results,
                "agentic_results": agentic_results,
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_markdown_agentic(basic_results, agentic_results, basic_summary, agentic_summary, changed, RESULTS_DIR / "agentic_v1.md")
    print(f"\nRe-saved {RESULTS_DIR / 'agentic_v1.json'} and {RESULTS_DIR / 'agentic_v1.md'} with {len(ids)} item(s) refreshed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["basic", "compare", "retry"], default="basic",
        help="basic (default): unchanged original behavior, writes baseline_v2.*. "
             "compare: runs both basic and agentic (REGS_MODE=agentic) and writes agentic_v1.*. "
             "retry: re-runs only --ids in agentic mode and merges into the existing agentic_v1.json.",
    )
    parser.add_argument("--ids", default="", help="Comma-separated item ids, for --mode retry.")
    args = parser.parse_args()
    if args.mode == "compare":
        asyncio.run(main_compare())
    elif args.mode == "retry":
        asyncio.run(main_retry_agentic([i.strip() for i in args.ids.split(",") if i.strip()]))
    else:
        asyncio.run(main())
