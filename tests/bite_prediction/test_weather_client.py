"""
Unit tests for the Visual Crossing response parsing in weather_client.py —
pure function, no network. Covers the is_storm/is_heavy_precip mapping
since that feeds directly into compute_bite_score's safety invariant.
"""

from datetime import datetime, timezone

from bite_prediction.providers.weather_client import _build_from_visual_crossing


def _epoch(hour: int) -> int:
    return int(datetime(2026, 7, 15, hour, 0, tzinfo=timezone.utc).timestamp())


def _hour(hour: int, *, icon="clear-day", precip=0.0, windgust=10.0) -> dict:
    return {
        "datetimeEpoch": _epoch(hour),
        "temp": 20.0, "feelslike": 20.0, "pressure": 1015.0,
        "windspeed": 8.0, "windgust": windgust, "cloudcover": 50.0,
        "precip": precip, "precipprob": 0.0, "icon": icon,
    }


def _weather(hours: list[dict]) -> dict:
    return {
        "tzoffset": 0,
        "days": [{
            "datetime": "2026-07-15",
            "sunriseEpoch": _epoch(6), "sunsetEpoch": _epoch(20),
            "hours": hours,
        }],
    }


def test_thunder_icon_sets_is_storm():
    weather = _weather([_hour(12, icon="thunder-rain")])
    data = _build_from_visual_crossing(weather, 0.0, 0.0, hours=1, tide_rates={})
    assert data.conditions[0].is_storm is True


def test_high_windgust_without_thunder_icon_sets_is_storm():
    # Real Hurricane Ian landfall data (2022-09-28, Fort Myers FL): icon
    # stayed "rain" all day despite 113 km/h gusts — icon alone misses this.
    weather = _weather([_hour(18, icon="rain", precip=5.7, windgust=105.5)])
    data = _build_from_visual_crossing(weather, 0.0, 0.0, hours=1, tide_rates={})
    assert data.conditions[0].is_storm is True


def test_heavy_rain_without_storm_sets_is_heavy_precip_only():
    weather = _weather([_hour(6, icon="rain", precip=13.5, windgust=15.0)])
    data = _build_from_visual_crossing(weather, 0.0, 0.0, hours=1, tide_rates={})
    cond = data.conditions[0]
    assert cond.is_heavy_precip is True
    assert cond.is_storm is False


def test_calm_clear_hour_sets_neither_flag():
    weather = _weather([_hour(12)])
    data = _build_from_visual_crossing(weather, 0.0, 0.0, hours=1, tide_rates={})
    cond = data.conditions[0]
    assert cond.is_storm is False
    assert cond.is_heavy_precip is False
