"""
question_parsing.py — regs_advisor.engine
----------------------------------------------
Lightweight "zone N" + species-name extraction for /regs/ask, so a
question like "walleye limits in zone 8" can be answered with real
numbers from the structured /regs/limits engine instead of only the
free-text KB retrieval, which has no per-zone data at all (see
docs/REGS_CHATBOT_PLAN.md "Phase 2 follow-ups"). This is the small,
bounded version of the deliberately-deferred multi-tool routing —
regex + keyword matching, not general NLU or an LLM tool-use call.
"""

import re

from regs_advisor.engine.zones import ZONE_NAME_TO_ID

# Most-specific-first so e.g. "largemouth bass" matches before the
# generic "bass" fallback. Mirrors the ~12 species already curated in
# knowledge_base/species_tackle.md — expanding that KB should expand
# this list too.
_SPECIES_KEYWORDS = [
    "largemouth bass", "smallmouth bass", "lake trout", "brook trout",
    "rainbow trout", "yellow perch", "black crappie", "lake sturgeon",
    "atlantic salmon", "landlocked salmon", "northern pike",
    "muskellunge", "muskie", "walleye", "sauger", "bass", "trout",
    "perch", "crappie", "sturgeon", "salmon", "pike", "musky",
]

_ZONE_NAME_LOOKUP = {name.lower(): name for name in ZONE_NAME_TO_ID}


def extract_zone(question: str) -> str | None:
    """Best-effort 'zone N[ suffix]' -> canonical zone name (e.g. 'Zone 27').
    Returns None for zones that don't cleanly resolve to one of the 34
    known names — including an unqualified 'zone 19', which is genuinely
    ambiguous between its 3 sub-zones and shouldn't guess."""
    match = re.search(r"zone\s*(\d+)\s*(north|south|east|west)?", question, re.IGNORECASE)
    if not match:
        return None
    num, suffix = match.group(1), match.group(2)
    candidate = f"zone {num}" + (f" {suffix.lower()}" if suffix else "")
    return _ZONE_NAME_LOOKUP.get(candidate)


def extract_species(question: str) -> str | None:
    """Best-effort species-keyword extraction, matched case-insensitively
    against the question text."""
    q = question.lower()
    for keyword in _SPECIES_KEYWORDS:
        if keyword in q:
            return keyword
    return None
