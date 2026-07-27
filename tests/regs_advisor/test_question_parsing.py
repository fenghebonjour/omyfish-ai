"""zone/species extraction for /regs/ask (regs_advisor.engine.question_parsing)."""

from regs_advisor.engine.question_parsing import extract_species, extract_zone


def test_extracts_plain_zone_number():
    assert extract_zone("walleye limits in zone 8") == "Zone 8"


def test_extracts_zone_with_directional_suffix():
    assert extract_zone("pike limits in zone 19 north") == "Zone 19 north"


def test_unqualified_ambiguous_zone_returns_none():
    # "Zone 19" alone is ambiguous between north/south-A/south-B — don't guess.
    assert extract_zone("limits in zone 19") is None


def test_unknown_zone_number_returns_none():
    assert extract_zone("limits in zone 99") is None


def test_no_zone_mentioned_returns_none():
    assert extract_zone("best lure for smallmouth bass") is None


def test_extracts_specific_species_before_generic_fallback():
    assert extract_species("largemouth bass limit in zone 8") == "largemouth bass"
    assert extract_species("any bass tips?") == "bass"


def test_extracts_walleye():
    assert extract_species("walleye limits in zone 8") == "walleye"


def test_no_species_mentioned_returns_none():
    assert extract_species("what's the rule in zone 8") is None
