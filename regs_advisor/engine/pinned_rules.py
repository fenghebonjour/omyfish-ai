"""
pinned_rules.py — regs_advisor.engine
--------------------------------------
REGS_FIX_PINNED (see router.py / engine/agentic.py): a short "core rules"
block of the must-know province-wide (all-species, all-zone) rules, meant to
be included in the LLM context regardless of what the per-question TF-IDF
retriever (retrieval.py, unmodified) ranks highest. Content lives in
knowledge_base/pinned_rules.json, not hardcoded here, so every rule's source
and the config's last_verified placeholder stay next to the KB files they're
drawn from.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "knowledge_base" / "pinned_rules.json"


def load_core_rules_block() -> str:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    lines = [
        "Core rules (always apply, regardless of species or zone). If a retrieved "
        "passage merely describes a technique and appears to conflict with one of "
        "these, the core rule below wins:"
    ]
    for rule in config["rules"]:
        lines.append(f"- {rule['text']} (source: {rule['source']})")
    return "\n".join(lines)
