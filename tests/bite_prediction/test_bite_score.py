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
