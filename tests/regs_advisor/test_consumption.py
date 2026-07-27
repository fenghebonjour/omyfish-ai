"""Pure logic for the consumption-advisory engine — no network."""

from regs_advisor.engine.consumption import (
    SpeciesAdvisoryRecord, Station, build_advisory, haversine_km, pick_size_class,
)

PIKE = SpeciesAdvisoryRecord(
    no_bqma="05090005", hydronyme="Saint-Charles, Lac", common_name="Grand brochet",
    scientific_name="Esox lucius", english_name="Northern pike", fishing_status="Autorisée",
    meals_per_month=[8, None, None], min_size_cm=[40, 55, 70],
)
STATION = Station(no_bqma="05090005", hydronyme="Saint-Charles, Lac", latitude=46.937665, longitude=-71.386639)


def test_haversine_zero_for_same_point():
    assert haversine_km(46.8, -71.2, 46.8, -71.2) == 0


def test_haversine_known_distance_quebec_montreal():
    # ~233 km great-circle between the two city centers
    d = haversine_km(46.8139, -71.2080, 45.5019, -73.5674)
    assert 220 < d < 250


def test_pick_size_class_uses_qualifying_bucket():
    size_class, meals = pick_size_class(PIKE, size_cm=45)
    assert size_class == "small"
    assert meals == 8


def test_pick_size_class_does_not_borrow_smaller_bucket_when_own_bucket_unsampled():
    # 60cm falls in the "medium" bucket by threshold, but medium has no
    # sampled meal count at this station — must report medium with no
    # data, never silently substitute "small"'s count (the source data
    # warns contaminant levels rise with size, so that would understate risk).
    size_class, meals = pick_size_class(PIKE, size_cm=60)
    assert size_class == "medium"
    assert meals is None


def test_pick_size_class_below_smallest_threshold():
    size_class, meals = pick_size_class(PIKE, size_cm=20)
    assert size_class is None
    assert meals is None


def test_pick_size_class_no_size_given_uses_smallest_sampled():
    size_class, meals = pick_size_class(PIKE, size_cm=None)
    assert size_class == "small"
    assert meals == 8


def test_build_advisory_includes_note_when_no_class_qualifies():
    advisory = build_advisory(STATION, distance_km=1.0, record=PIKE, size_cm=20)
    assert advisory.meals_per_month is None
    assert "smaller than the sampled size range" in advisory.note


def test_build_advisory_no_note_when_class_qualifies():
    advisory = build_advisory(STATION, distance_km=1.0, record=PIKE, size_cm=45)
    assert advisory.meals_per_month == 8
    assert advisory.note is None
