"""
run_fixes_eval.py — flag comparison runner for the live-bait diagnosis.

Does NOT modify eval/run_eval.py. Reuses its frozen grading functions
(retrieval_hit_at_3, answer_correctness, summarize, run_one, run_one_agentic)
unmodified, and only adds: per-flag-combo env var toggling, a restricted
item list for agentic mode (Groq daily-token-limit guard), Groq token-usage
tracking via a process-local monkeypatch (never touches repo source files),
and its own output files under eval/results/ so it never overwrites
baseline_v2.* / agentic_v1.* from prior work.

Flags A (REGS_FIX_CHUNKING) and B (REGS_FIX_GLOSSARY) are not implemented --
see eval/results/diagnosis_live_bait.md: the diagnosis did not confirm
chunking/ranking as a root cause of the live-bait failure once the missing
KB content was added, so only C (REGS_FIX_PINNED) and D (REGS_FIX_GUARDRAIL)
exist as flags. Combos run: baseline, C, D, C+D (table's "A+B+C+D" column is
reported as "C+D" accordingly).

Usage:
    cd /home/bigblue/omyfish-ai && python3 eval/run_fixes_eval.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import groq  # noqa: E402
from groq.resources.chat.completions import Completions  # noqa: E402

from eval.run_eval import (  # noqa: E402
    EVAL_PATH, _fmt_pct, run_one, run_one_agentic, summarize,
)

RESULTS_DIR = Path(__file__).parent / "results"

AGENTIC_ITEM_IDS = {"T3", "H2", "W1", "O1", "T2"}  # previously-failing items named by the user

COMBOS = [
    ("baseline", {}),
    ("C", {"REGS_FIX_PINNED": "1"}),
    ("D", {"REGS_FIX_GUARDRAIL": "1"}),
    ("C+D", {"REGS_FIX_PINNED": "1", "REGS_FIX_GUARDRAIL": "1"}),
]
FLAG_VARS = ["REGS_FIX_PINNED", "REGS_FIX_GUARDRAIL", "REGS_MODE"]

# ── Process-local Groq usage tracking — monkeypatches the SDK's resource ──
# ── class for this run only; no repo source file is touched.            ──
usage = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
_orig_create = Completions.create


def _tracked_create(self, *args, **kwargs):
    response = _orig_create(self, *args, **kwargs)
    u = getattr(response, "usage", None)
    if u is not None:
        usage["total_tokens"] += u.total_tokens or 0
        usage["prompt_tokens"] += u.prompt_tokens or 0
        usage["completion_tokens"] += u.completion_tokens or 0
    usage["calls"] += 1
    return response


def _set_env(flags: dict) -> None:
    for var in FLAG_VARS:
        os.environ.pop(var, None)
    for k, v in flags.items():
        os.environ[k] = v


async def run_basic_combo(items: list[dict]) -> list[dict]:
    os.environ.pop("REGS_MODE", None)
    results = []
    for item in items:
        r = await run_one(item)
        results.append(r)
        tag = "OK" if r["correctness"]["passed"] else "FAIL"
        print(f"  [{tag}] {r['id']}")
    return results


async def run_agentic_combo(items: list[dict]) -> list[dict]:
    os.environ["REGS_MODE"] = "agentic"
    results = []
    for item in items:
        r = await run_one_agentic(item)
        results.append(r)
        tag = "OK" if r["correctness"]["passed"] else "FAIL"
        print(f"  [{tag}] {r['id']}  tool_calls={r['tool_call_count']}")
    os.environ.pop("REGS_MODE", None)
    return results


async def main() -> None:
    Completions.create = _tracked_create
    try:
        eval_data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        all_items = eval_data["items"]
        agentic_items = [it for it in all_items if it["id"] in AGENTIC_ITEM_IDS or it["tier"] == "regression"]

        basic_by_combo: dict[str, list[dict]] = {}
        agentic_by_combo: dict[str, list[dict]] = {}

        for name, flags in COMBOS:
            print(f"\n=== basic mode, flags={name} (full eval, n={len(all_items)}) ===")
            _set_env(flags)
            basic_by_combo[name] = await run_basic_combo(all_items)

            print(f"\n=== agentic mode, flags={name} (regression + {sorted(AGENTIC_ITEM_IDS)}, n={len(agentic_items)}) ===")
            _set_env(flags)
            agentic_by_combo[name] = await run_agentic_combo(agentic_items)

        _set_env({})  # leave flags off on exit
    finally:
        Completions.create = _orig_create

    report = {
        "basic": {name: {"summary": summarize(rs), "results": rs} for name, rs in basic_by_combo.items()},
        "agentic": {name: {"summary": summarize(rs), "results": rs} for name, rs in agentic_by_combo.items()},
        "groq_usage_this_run": usage,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "fixes_comparison.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = ["# Live-bait fix comparison — basic & agentic, per flag combo", ""]
    lines.append(f"Groq usage this run: {usage['calls']} calls, {usage['total_tokens']} total tokens "
                 f"({usage['prompt_tokens']} prompt + {usage['completion_tokens']} completion).")
    lines.append("")
    lines.append("Flags A (chunking) and B (glossary) are not implemented -- diagnosis did not confirm "
                  "them as root causes once the missing KB content was added. See diagnosis_live_bait.md.")
    lines.append("")

    lines.append("## Basic mode — full eval (n=%d)" % len(all_items))
    lines.append("")
    lines.append("| flags | overall correctness | regression tier correctness | hard tier correctness |")
    lines.append("|---|---|---|---|")
    for name, _ in COMBOS:
        s = summarize(basic_by_combo[name])
        _, overall_c = _fmt_pct(s["overall"])
        _, reg_c = _fmt_pct(s["by_tier"].get("regression", {"correctness": None, "correctness_fraction": "n/a"}))
        _, hard_c = _fmt_pct(s["by_tier"].get("hard", {"correctness": None, "correctness_fraction": "n/a"}))
        lines.append(f"| {name} | {overall_c} | {reg_c} | {hard_c} |")
    lines.append("")

    lines.append("## Basic mode — live-bait items only (RB1-RB9)")
    lines.append("")
    lines.append("| flags | " + " | ".join(f"RB{i}" for i in range(1, 10)) + " |")
    lines.append("|---|" + "---|" * 9)
    for name, _ in COMBOS:
        by_id = {r["id"]: r for r in basic_by_combo[name]}
        cells = ["OK" if by_id[f"RB{i}"]["correctness"]["passed"] else "FAIL" for i in range(1, 10)]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Agentic mode — regression tier + T3/H2/W1/O1/T2 (n=%d)" % len(agentic_items))
    lines.append("")
    lines.append("| flags | overall correctness |")
    lines.append("|---|---|")
    for name, _ in COMBOS:
        s = summarize(agentic_by_combo[name])
        _, overall_c = _fmt_pct(s["overall"])
        lines.append(f"| {name} | {overall_c} |")
    lines.append("")

    lines.append("## Per-item results that changed vs. baseline (either mode)")
    lines.append("")
    any_change = False
    for mode_name, by_combo in [("basic", basic_by_combo), ("agentic", agentic_by_combo)]:
        base_by_id = {r["id"]: r["correctness"]["passed"] for r in by_combo["baseline"]}
        for name, _ in COMBOS[1:]:
            for r in by_combo[name]:
                base = base_by_id.get(r["id"])
                now = r["correctness"]["passed"]
                if base is not None and base != now:
                    any_change = True
                    arrow = "FAIL -> OK" if (not base and now) else "OK -> FAIL"
                    lines.append(f"- [{mode_name}] **{r['id']}** baseline vs {name}: {arrow}")
    if not any_change:
        lines.append("None.")
    lines.append("")

    (RESULTS_DIR / "fixes_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSaved {RESULTS_DIR / 'fixes_comparison.json'} and {RESULTS_DIR / 'fixes_comparison.md'}")
    print(f"Groq usage this run: {usage}")


if __name__ == "__main__":
    asyncio.run(main())
