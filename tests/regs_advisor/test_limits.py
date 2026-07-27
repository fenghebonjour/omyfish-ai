"""
Parsing of the RegPec "Reglements" HTML grid (regs_advisor.engine.limits).

zone27_reglements.html is a trimmed excerpt of a real response captured
2026-07-26 from peche.faune.gouv.qc.ca/RegPec/en/Info/Reglements?id_zone=31
(see docs/REGS_CHATBOT_PLAN.md Phase 0) — real markup, not hand-written,
so the parser is exercised against the actual DevExpress row/class shapes.
"""

from pathlib import Path

from regs_advisor.engine.limits import find_species_limit, parse_limits_html

FIXTURE = Path(__file__).parent / "fixtures" / "zone27_reglements.html"


def _parse():
    return parse_limits_html(FIXTURE.read_text(encoding="utf-8"), zone_name="Zone 27")


def test_parses_all_general_zone_rows():
    zl = _parse()
    assert len(zl.general_rules) == 18


def test_species_with_prohibited_catch_limit():
    zl = _parse()
    salmon = find_species_limit(zl, "Atlantic salmon")
    assert len(salmon) == 1
    assert salmon[0].catch_limit == "Fishing prohibited"
    assert salmon[0].length_limit is None


def test_species_with_length_limit_and_device():
    zl = _parse()
    walleye = find_species_limit(zl, "walleye")
    assert len(walleye) == 1
    r = walleye[0]
    assert r.catch_limit == "6 in all"
    assert "37 cm to 53 cm" in r.length_limit
    assert r.fishing_device == "Angling only"
    assert r.period == "From May 15th, 2026 to November 30th, 2026"


def test_unmatched_species_returns_empty():
    zl = _parse()
    assert find_species_limit(zl, "narwhal") == []


# ── Synthetic HTML: exercises section filtering deterministically,      ──
# ── independent of how a re-scrape of the real page happens to trim.    ──

_SYNTHETIC_HTML = """
<table>
<tr class="dxgvGroupRow_RegPecTheme table-level1 gras"><td>Rules for the zone</td></tr>
<tr class="dxgvGroupRow_RegPecTheme table-level2"><td>Period From May 1st, 2026 to Sept 1st, 2026</td></tr>
<tr class="dxgvDataRow_RegPecTheme">
  <td></td><td></td><td><div><span>Yellow perch</span></div></td><td>50</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
</tr>
<tr class="dxgvGroupRow_RegPecTheme table-level1 gras"><td>Lake Example ( 46&#176;00'00" N., 71&#176;00'00" W. )</td></tr>
<tr class="dxgvGroupRow_RegPecTheme table-level2"><td>Period From May 1st, 2026 to Sept 1st, 2026</td></tr>
<tr class="dxgvDataRow_RegPecTheme">
  <td></td><td></td><td><div><span>Yellow perch</span></div></td><td>10</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
</tr>
</table>
"""


def test_waterbody_exceptions_excluded_from_general_rules():
    zl = parse_limits_html(_SYNTHETIC_HTML, zone_name="Zone X")
    assert len(zl.general_rules) == 1
    assert zl.general_rules[0].catch_limit == "50"


def test_waterbody_exceptions_listed_by_name():
    zl = parse_limits_html(_SYNTHETIC_HTML, zone_name="Zone X")
    assert any("Lake Example" in s for s in zl.other_sections)
