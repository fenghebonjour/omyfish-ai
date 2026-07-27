"""
zones.py — regs_advisor.engine
--------------------------------
Resolves a lat/lon to a Quebec sport-fishing zone, and a zone name to
the internal `id_zone` the limits search (RegPec) expects.

Two different subsystems use two different internal IDs for the same
zone (confirmed 2026-07-26, see docs/REGS_CHATBOT_PLAN.md Phase 0):
the polygon layer's ID_ZONE (e.g. 2651) is not the limits search's
id_zone (e.g. 31). Match on the human-readable zone name instead.

ZONE_NAME_TO_ID is scraped once from the static <select> options embedded
in https://peche.faune.gouv.qc.ca/regpec/en/info/reglements (34 zones,
boundaries/names essentially never change year to year) rather than
re-fetched per request.
"""

from dataclasses import dataclass
from typing import Optional

ZONE_NAME_TO_ID: dict[str, int] = {
    "Zone 1": 1,
    "Zone 2": 2,
    "Zone 3": 3,
    "Zone 4": 4,
    "Zone 5": 5,
    "Zone 6": 6,
    "Zone 7": 7,
    "Zone 8": 8,
    "Zone 9": 9,
    "Zone 10": 10,
    "Zone 11": 11,
    "Zone 12": 12,
    "Zone 13 east": 13,
    "Zone 13 west": 14,
    "Zone 14": 15,
    "Zone 15": 16,
    "Zone 16": 17,
    "Zone 17": 18,
    "Zone 18": 19,
    "Zone 19 north": 3063,
    "Zone 19 south - part A": 2652,
    "Zone 19 south - part B": 2653,
    "Zone 20": 22,
    "Zone 21": 23,
    "Zone 22 north": 24,
    "Zone 22 south": 25,
    "Zone 23 north": 26,
    "Zone 23 south": 27,
    "Zone 24": 28,
    "Zone 25": 29,
    "Zone 26": 30,
    "Zone 27": 31,
    "Zone 28": 32,
    "Zone 29": 33,
}


@dataclass
class ZoneMatch:
    zone_name: str          # e.g. "Zone 27" — as returned by the polygon layer
    id_zone: Optional[int]  # id_zone for the limits search, if resolvable
    info_url: Optional[str] # official quebec.ca page for this zone's rules


def resolve_zone_id(zone_name: str) -> Optional[int]:
    """Map a polygon-layer zone name (e.g. 'Zone 19 south - part A') to
    the limits search's id_zone. Returns None if the name isn't in the
    static table (shouldn't happen for on-land Quebec coordinates)."""
    return ZONE_NAME_TO_ID.get(zone_name)
