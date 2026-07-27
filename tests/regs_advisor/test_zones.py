"""Zone name -> id_zone resolution (regs_advisor.engine.zones)."""

from regs_advisor.engine.zones import ZONE_NAME_TO_ID, resolve_zone_id


def test_resolves_known_zone_name():
    assert resolve_zone_id("Zone 27") == 31


def test_resolves_split_zone_name():
    # Zones 13/19/22/23 are split (east/west, north/south, part A/B) —
    # these use the exact string the polygon layer returns.
    assert resolve_zone_id("Zone 19 north") == 3063
    assert resolve_zone_id("Zone 19 south - part A") == 2652


def test_unknown_zone_name_returns_none():
    assert resolve_zone_id("Zone 99") is None


def test_every_mapped_id_is_unique():
    ids = list(ZONE_NAME_TO_ID.values())
    assert len(ids) == len(set(ids))
