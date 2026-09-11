"""
Router-level tests — the weather provider is monkeypatched so these never hit a live
network call (mirrors tests/regs_advisor/test_router.py's pattern). Engine scoring itself
is covered by test_bite_score.py/test_peak_windows.py; this file exercises the HTTP layer
those don't (BACKLOG.md item G, WEAKNESS_AUDIT.md — closes the "no route-level test for
/bite-score/*" testing gap).
"""

from datetime import datetime, time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import bite_prediction.router as router_module
from bite_prediction.engine import HourlyConditions
from bite_prediction.providers.weather_client import (
    CurrentConditions, ForecastData, SunTimes, WeatherProviderError,
)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def _condition(**overrides) -> HourlyConditions:
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


def _forecast_data() -> ForecastData:
    return ForecastData(
        conditions=[_condition(timestamp=datetime(2026, 7, 15, h, 0)) for h in range(6, 9)],
        sun_times=[SunTimes(date="2026-07-15", sunrise=datetime(2026, 7, 15, 5, 30),
                             sunset=datetime(2026, 7, 15, 20, 45))],
        current=CurrentConditions(time=datetime(2026, 7, 15, 6, 0), precipitation_mm=0,
                                   is_storm=False, is_heavy_precip=False),
    )


def test_forecast_returns_hourly_scores(client, monkeypatch):
    async def fake_fetch(lat, lon, hours):
        return _forecast_data()

    monkeypatch.setattr(router_module, "fetch_hourly_conditions", fake_fetch)

    r = client.get("/bite-score/forecast", params={"lat": 46.8, "lon": -71.2})

    assert r.status_code == 200
    body = r.json()
    assert body["species"] == "general"
    assert len(body["hourly"]) == 3
    assert "breakdown" in body["hourly"][0]


def test_forecast_unknown_species_returns_400(client):
    r = client.get("/bite-score/forecast", params={"lat": 46.8, "lon": -71.2, "species": "not-a-real-species"})

    assert r.status_code == 400


def test_forecast_weather_provider_down_returns_503(client, monkeypatch):
    async def fake_fetch(lat, lon, hours):
        raise WeatherProviderError("upstream unavailable")

    monkeypatch.setattr(router_module, "fetch_hourly_conditions", fake_fetch)

    r = client.get("/bite-score/forecast", params={"lat": 46.8, "lon": -71.2})

    assert r.status_code == 503


def test_today_delegates_to_forecast_with_24h_window(client, monkeypatch):
    captured = {}

    async def fake_fetch(lat, lon, hours):
        captured["hours"] = hours
        return _forecast_data()

    monkeypatch.setattr(router_module, "fetch_hourly_conditions", fake_fetch)

    r = client.get("/bite-score/today", params={"lat": 46.8, "lon": -71.2})

    assert r.status_code == 200
    assert captured["hours"] == 24


def test_species_key_resolves_known_alias(client):
    r = client.get("/bite-score/species-key", params={"name": "walleye"})

    assert r.status_code == 200
    body = r.json()
    assert body["matched"] is True
    assert body["species_key"]


def test_species_key_falls_back_to_general_for_unknown_name(client):
    r = client.get("/bite-score/species-key", params={"name": "definitely not a fish"})

    assert r.status_code == 200
    body = r.json()
    assert body["matched"] is False
    assert body["species_key"] == "general"
