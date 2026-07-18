"""
Unit tests for the bite_prediction engine — pure functions, no network,
no fixtures beyond plain dataclasses. Port smoke_test.py's scenarios in
here as real assertions once you're ready.
"""

from datetime import datetime, time

from bite_prediction.engine import HourlyConditions, compute_bite_score
from bite_prediction.engine.species_profiles import TemperatureBand
from bite_prediction.engine.bite_score import score_pressure, score_wind, score_temperature


def _base_conditions(**overrides) -> HourlyConditions:
    defaults = dict(
        timestamp=datetime(2026, 7, 15, 6, 0),
        air_temp_c=20, feels_like_c=20,
        pressure_hpa=1017, pressure_delta_3h=0, pressure_delta_24h=0,
        wind_speed_kmh=12, cloud_cover_pct=60, precip_mm=0, is_storm=False,
        moon_phase=0.5, minutes_from_moon_major=200, minutes_from_moon_minor=200,
        lake_level_trend_cm_per_day=1, tide_rate_m_per_hr=None,
        sunrise=time(5, 30), sunset=time(20, 45),
    )
    defaults.update(overrides)
    return HourlyConditions(**defaults)


def test_slow_pressure_fall_scores_higher_than_sharp_rise():
    falling = score_pressure(1017, delta_3h=-1.5, delta_24h=-3)
    rising = score_pressure(1017, delta_3h=3.0, delta_24h=5)
    assert falling > rising


def test_wind_peak_beats_calm_and_gale():
    peak = score_wind(12)
    calm = score_wind(0)
    gale = score_wind(45)
    assert peak > calm
    assert peak > gale


def test_temperature_outside_band_is_zero():
    band = TemperatureBand(min_ok=10, opt_low=18, opt_high=23, max_ok=27)
    assert score_temperature(5, band) == 0.0
    assert score_temperature(20, band) == 100.0


def test_storm_flag_forces_low_score_and_safety_message():
    cond = _base_conditions(is_storm=True)
    result = compute_bite_score(cond, species_key="general")
    assert result.safety_flag is not None
    assert result.score < 40


def test_breakdown_always_present():
    cond = _base_conditions()
    result = compute_bite_score(cond, species_key="smallmouth_bass")
    d = result.breakdown.as_dict()
    assert set(d.keys()) == {"pressure", "temperature", "wind", "water", "solunar", "sky"}


def test_heavy_precip_caps_score_and_sets_safety_message():
    result = compute_bite_score(_base_conditions(is_heavy_precip=True))
    assert result.score <= 35.0
    assert result.safety_flag is not None
    assert "not recommended" in result.safety_flag


def test_storm_outranks_heavy_precip():
    result = compute_bite_score(_base_conditions(is_storm=True, is_heavy_precip=True))
    assert result.score <= 15.0
    assert "lightning" in result.safety_flag


def _ideal_conditions(**overrides) -> HourlyConditions:
    """Every factor near its optimum, at dawn for the crepuscular boost —
    the adversarial input for the safety caps."""
    return _base_conditions(
        timestamp=datetime(2026, 7, 15, 5, 45),
        pressure_delta_3h=-1.5, pressure_delta_24h=-3,
        cloud_cover_pct=60, precip_mm=1.0,
        minutes_from_moon_major=0,
        **overrides,
    )


def test_storm_cap_holds_even_under_otherwise_ideal_conditions():
    ideal = compute_bite_score(_ideal_conditions())
    stormy = compute_bite_score(_ideal_conditions(is_storm=True))
    assert ideal.score > 15.0  # the cap is actually doing work
    assert stormy.score <= 15.0
    assert "lightning" in stormy.safety_flag


def test_heavy_precip_cap_holds_even_under_otherwise_ideal_conditions():
    result = compute_bite_score(_ideal_conditions(is_heavy_precip=True))
    assert result.score <= 35.0
    assert result.safety_flag == "Heavy precipitation — fishing not recommended this hour."


def test_capped_result_keeps_full_breakdown():
    # Product invariant: safety caps suppress the headline score only —
    # the six-factor breakdown must never be collapsed or zeroed.
    result = compute_bite_score(_base_conditions(is_storm=True))
    assert set(result.breakdown.as_dict().keys()) == {
        "pressure", "temperature", "wind", "water", "solunar", "sky"}
    assert set(result.weighted_contribution.keys()) == set(result.breakdown.as_dict().keys())


def test_calm_weather_has_no_safety_flag():
    assert compute_bite_score(_base_conditions()).safety_flag is None


def test_light_rain_boosts_sky_but_heavy_rain_penalizes():
    from bite_prediction.engine.bite_score import score_sky
    light = score_sky(_base_conditions(precip_mm=2.0))
    heavy = score_sky(_base_conditions(precip_mm=2.1))
    dry = score_sky(_base_conditions(precip_mm=0))
    assert light > dry
    assert heavy < dry


def _hourly_results(*hour_overrides):
    from bite_prediction.engine.bite_score import compute_bite_score
    return [
        compute_bite_score(_base_conditions(
            timestamp=datetime(2026, 7, 15, hour), **overrides))
        for hour, overrides in hour_overrides
    ]


def test_best_windows_never_recommends_flagged_hours():
    from bite_prediction.engine.bite_score import best_windows
    # A miserable week: the storm hour's capped 15 outscores every calm hour,
    # but a lightning hour must never surface as a recommended window.
    awful = dict(
        air_temp_c=2, pressure_hpa=1030, pressure_delta_3h=3.0, pressure_delta_24h=6,
        wind_speed_kmh=50, cloud_cover_pct=0, moon_phase=0.25,
        minutes_from_moon_major=400, minutes_from_moon_minor=400,
        lake_level_trend_cm_per_day=-8,
    )
    results = _hourly_results(
        (6, dict(is_storm=True, minutes_from_moon_major=0, pressure_delta_3h=-1.5)),
        (10, dict(awful)),
        (14, dict(awful)),
    )
    storm, *calm = results
    assert storm.score > max(r.score for r in calm)  # storm would win on score alone
    chosen = best_windows(results, top_n=2)
    assert storm not in chosen
    assert all(r.safety_flag is None for r in chosen)


def test_best_windows_empty_when_every_hour_is_flagged():
    from bite_prediction.engine.bite_score import best_windows
    results = _hourly_results(
        (6, dict(is_storm=True)),
        (9, dict(is_heavy_precip=True)),
    )
    assert best_windows(results) == []
