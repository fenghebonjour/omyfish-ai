"""
weather_client.py — bite_prediction.providers
-----------------------------------------------
The one adapter boundary this domain has: fetching hourly weather/tide
data and shaping it into the engine's HourlyConditions struct.

Providers (chosen 2026-07-15):
  - Weather: Open-Meteo (free, no key) — hourly temperature, apparent
    temperature, sea-level pressure, wind, cloud cover, precipitation,
    and weather_code (95/96/99 = thunderstorm -> is_storm).
  - Tides: NOAA CO-OPS (free, no key) — hourly predicted heights from
    the nearest tide station within ~50 km, turned into a signed
    rate-of-change. No station in range (inland/non-US water) -> both
    water fields stay None and the engine falls back to its neutral
    water score. A NOAA outage degrades the same way instead of failing
    the whole forecast.
  - Solunar: computed locally with `ephem` (pure astronomy, no network).

Swap the implementation here if a vendor changes — nothing in engine/
or router.py needs to know.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import ephem
import httpx

from bite_prediction.engine import HourlyConditions

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NOAA_STATIONS_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    "?type=tidepredictions"
)
NOAA_PREDICTIONS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

MAX_TIDE_STATION_KM = 50.0
_HTTP_TIMEOUT = 10.0
_STORM_WEATHER_CODES = {95, 96, 99}  # WMO thunderstorm codes

# NOAA tide-prediction station list (~3k stations); fetched once per process.
_stations_cache: list[dict] | None = None


class WeatherProviderError(RuntimeError):
    """Raised when the weather provider (the one mandatory feed) fails."""


@dataclass
class SunTimes:
    date: str           # ISO date
    sunrise: datetime   # local naive
    sunset: datetime


@dataclass
class ForecastData:
    conditions: list[HourlyConditions]
    sun_times: list[SunTimes]  # per-day sunrise/sunset (drives the dawn/dusk boost)


async def fetch_hourly_conditions(lat: float, lon: float, hours: int) -> ForecastData:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        weather = await _fetch_open_meteo(client, lat, lon)
        # Tides are optional enrichment: any failure means None water fields,
        # which the engine scores as a neutral default.
        try:
            tide_rates = await _fetch_tide_rates(client, lat, lon)
        except Exception:
            tide_rates = {}

    utc_offset = timedelta(seconds=weather["utc_offset_seconds"])
    hourly = weather["hourly"]
    sun_times = [
        SunTimes(date=d, sunrise=datetime.fromisoformat(rise), sunset=datetime.fromisoformat(set_))
        for d, rise, set_ in zip(weather["daily"]["time"],
                                 weather["daily"]["sunrise"], weather["daily"]["sunset"])
    ]
    sun_by_date = {s.date: (s.sunrise.time(), s.sunset.time()) for s in sun_times}

    timestamps = [datetime.fromisoformat(t) for t in hourly["time"]]  # local naive
    pressures = hourly["pressure_msl"]
    now_local = datetime.utcnow() + utc_offset

    # Anchor at local midnight, not "now": clients chart the whole current
    # day, so today's already-elapsed hours are included. Earlier hours
    # (yesterday) were only fetched to compute pressure deltas.
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    conditions: list[HourlyConditions] = []
    for i, ts in enumerate(timestamps):
        if ts < day_start_local:
            continue
        if len(conditions) >= hours:
            break

        ts_utc = ts - utc_offset
        moon = _moon_metrics(lat, lon, ts_utc)
        sunrise, sunset = sun_by_date.get(ts.date().isoformat(), (None, None))

        conditions.append(HourlyConditions(
            timestamp=ts,
            air_temp_c=hourly["temperature_2m"][i],
            feels_like_c=hourly["apparent_temperature"][i],
            pressure_hpa=pressures[i],
            pressure_delta_3h=pressures[i] - pressures[i - 3] if i >= 3 else 0.0,
            pressure_delta_24h=pressures[i] - pressures[i - 24] if i >= 24 else 0.0,
            wind_speed_kmh=hourly["wind_speed_10m"][i],
            cloud_cover_pct=hourly["cloud_cover"][i],
            precip_mm=hourly["precipitation"][i],
            is_storm=hourly["weather_code"][i] in _STORM_WEATHER_CODES,
            moon_phase=moon["phase"],
            minutes_from_moon_major=moon["minutes_from_major"],
            minutes_from_moon_minor=moon["minutes_from_minor"],
            tide_rate_m_per_hr=tide_rates.get(ts_utc.replace(minute=0)),
            lake_level_trend_cm_per_day=None,  # no lake-level feed yet
            sunrise=sunrise,
            sunset=sunset,
        ))

    return ForecastData(conditions=conditions, sun_times=sun_times)


# --------------------------------------------------------------------------- #
# Open-Meteo (weather — mandatory)
# --------------------------------------------------------------------------- #

async def _fetch_open_meteo(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m", "apparent_temperature", "pressure_msl",
            "wind_speed_10m", "cloud_cover", "precipitation", "weather_code",
        ]),
        "daily": "sunrise,sunset",
        "timezone": "auto",
        "past_days": 1,       # history for the 3h/24h pressure deltas
        "forecast_days": 16,  # 14-day horizon regardless of time of day (16 = Open-Meteo max)
    }
    try:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise WeatherProviderError(f"Open-Meteo request failed: {e}") from e
    if "hourly" not in data or "daily" not in data:
        raise WeatherProviderError(f"Open-Meteo response missing hourly/daily data: {data}")
    return data


# --------------------------------------------------------------------------- #
# NOAA CO-OPS (tides — optional; inland water simply has no nearby station)
# --------------------------------------------------------------------------- #

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


async def _nearest_tide_station(client: httpx.AsyncClient, lat: float, lon: float) -> str | None:
    global _stations_cache
    if _stations_cache is None:
        resp = await client.get(NOAA_STATIONS_URL)
        resp.raise_for_status()
        # Reference ("R") stations only: subordinate stations can't serve the
        # hourly-interval predictions the rate calculation needs.
        _stations_cache = [
            {"id": s["id"], "lat": s["lat"], "lon": s["lng"]}
            for s in resp.json().get("stations", []) if s.get("type") == "R"
        ]
    best_id, best_km = None, MAX_TIDE_STATION_KM
    for s in _stations_cache:
        km = _haversine_km(lat, lon, s["lat"], s["lon"])
        if km < best_km:
            best_id, best_km = s["id"], km
    return best_id


async def _fetch_tide_rates(client: httpx.AsyncClient, lat: float, lon: float) -> dict[datetime, float]:
    """Hourly signed tide rate (m/hr) keyed by UTC hour, from the nearest
    station's predicted heights via centered differences. Empty dict if no
    station is within range."""
    station = await _nearest_tide_station(client, lat, lon)
    if station is None:
        return {}

    today = datetime.utcnow().date()
    params = {
        "product": "predictions", "application": "omyfish", "format": "json",
        "station": station, "datum": "MLLW", "units": "metric",
        "time_zone": "gmt", "interval": "h",
        "begin_date": today.strftime("%Y%m%d"),
        "end_date": (today + timedelta(days=15)).strftime("%Y%m%d"),
    }
    resp = await client.get(NOAA_PREDICTIONS_URL, params=params)
    resp.raise_for_status()
    preds = resp.json().get("predictions", [])
    if len(preds) < 3:
        return {}

    times = [datetime.strptime(p["t"], "%Y-%m-%d %H:%M") for p in preds]
    heights = [float(p["v"]) for p in preds]
    rates: dict[datetime, float] = {}
    for i, t in enumerate(times):
        lo, hi = max(i - 1, 0), min(i + 1, len(times) - 1)
        span_hr = (times[hi] - times[lo]).total_seconds() / 3600
        if span_hr > 0:
            rates[t] = (heights[hi] - heights[lo]) / span_hr
    return rates


# --------------------------------------------------------------------------- #
# Solunar (local astronomy — no network)
# --------------------------------------------------------------------------- #

def _moon_metrics(lat: float, lon: float, ts_utc: datetime) -> dict:
    """Moon cycle fraction (0=new, 0.5=full) plus minutes to the nearest
    major (transit/antitransit) and minor (rise/set) solunar event."""
    date = ephem.Date(ts_utc)
    prev_new, next_new = ephem.previous_new_moon(date), ephem.next_new_moon(date)
    phase = (date - prev_new) / (next_new - prev_new)

    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = date
    moon = ephem.Moon()

    def _nearest_minutes(events) -> float:
        deltas = []
        for fn in events:
            try:
                deltas.append(abs(fn(moon) - date) * 24 * 60)
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                continue
        return min(deltas) if deltas else 720.0  # polar edge case: no event

    major = _nearest_minutes([obs.previous_transit, obs.next_transit,
                              obs.previous_antitransit, obs.next_antitransit])
    minor = _nearest_minutes([obs.previous_rising, obs.next_rising,
                              obs.previous_setting, obs.next_setting])
    return {"phase": phase, "minutes_from_major": major, "minutes_from_minor": minor}
