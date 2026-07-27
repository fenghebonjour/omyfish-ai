"""
limits.py — regs_advisor.engine
----------------------------------
Parses the DevExpress-rendered HTML grid returned by the RegPec
"Reglements" page (confirmed 2026-07-26, see docs/REGS_CHATBOT_PLAN.md
Phase 0) into structured catch/possession/length-limit records.

The grid has two nesting levels:
  table-level1 ("gras") — a section: either "Rules for the zone"
    (the general rules that apply everywhere in the zone) or a named
    waterbody exception (e.g. "Lake Saint-Joseph ( ... )").
  table-level2 — a "Period From X to Y" sub-group within a section.
  dxgvDataRow  — one species row: species, catch limit, length limit,
    fishing device, note (fixed column order, some cells legitimately
    empty — do not infer position from get_text() alone).

Phase 1 only surfaces the general zone-wide section (`GENERAL_SECTION_LABEL`);
per-waterbody exceptions exist in the same page but are out of scope until
Phase 3 (per the plan doc — same data the Map tab will overlay).
"""

from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

GENERAL_SECTION_LABEL = "Rules for the zone"


@dataclass
class SpeciesLimit:
    section: str            # "Rules for the zone" or a named waterbody exception
    period: str              # raw period text, e.g. "From May 15th, 2026 to November 30th, 2026"
    species: str
    catch_limit: str
    length_limit: Optional[str]
    fishing_device: Optional[str]
    note: Optional[str]


@dataclass
class ZoneLimits:
    zone_name: str
    general_rules: list[SpeciesLimit]
    other_sections: list[str]  # names of waterbody-exception sections present but not parsed


def _cell(tds, i: int) -> Optional[str]:
    text = tds[i].get_text(" ", strip=True)
    return text or None


def parse_limits_html(html: str, zone_name: str) -> ZoneLimits:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(
        "tr.dxgvGroupRow_RegPecTheme.table-level1, "
        "tr.dxgvGroupRow_RegPecTheme.table-level2, "
        "tr.dxgvDataRow_RegPecTheme"
    )

    general_rules: list[SpeciesLimit] = []
    other_sections: list[str] = []
    current_section: Optional[str] = None
    current_period: str = ""

    for row in rows:
        classes = row.get("class", [])
        if "table-level1" in classes:
            current_section = row.get_text(" ", strip=True)
            current_period = ""
            if current_section != GENERAL_SECTION_LABEL:
                other_sections.append(current_section)
            continue
        if "table-level2" in classes:
            current_period = row.get_text(" ", strip=True).removeprefix("Period").strip()
            continue

        # dxgvDataRow — only keep rows under the general section
        if current_section != GENERAL_SECTION_LABEL:
            continue
        tds = row.find_all("td")
        if len(tds) < 7:
            continue
        species = _cell(tds, 2)
        catch_limit = _cell(tds, 3)
        if not species or not catch_limit:
            continue
        general_rules.append(SpeciesLimit(
            section=current_section,
            period=current_period,
            species=species,
            catch_limit=catch_limit,
            length_limit=_cell(tds, 4),
            fishing_device=_cell(tds, 5),
            note=_cell(tds, 6),
        ))

    return ZoneLimits(zone_name=zone_name, general_rules=general_rules, other_sections=other_sections)


def find_species_limit(zone_limits: ZoneLimits, species_query: str) -> list[SpeciesLimit]:
    """Case-insensitive substring match against the species column — the
    grid groups related species under one label (e.g. 'Walleye and sauger',
    'Char (arctic char, brook trout)'), so exact-match would miss them."""
    q = species_query.lower()
    return [r for r in zone_limits.general_rules if q in r.species.lower()]
