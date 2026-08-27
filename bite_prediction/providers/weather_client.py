"""
weather_client.py — bite_prediction.providers
-----------------------------------------------
The one adapter boundary this domain has: fetching hourly weather/tide
data and shaping it into the engine's HourlyConditions struct.

Providers (weather: Visual Crossing primary, Open-Meteo then OpenWeatherMap
as a fallback chain — Visual Crossing added 2026-08-27 as the primary
because its free tier counts a full 15-day hourly forecast as a single
"record" against the 1,000/day quota, rather than being IP-throttled like
Open-Meteo was on HF Spaces):
  - Weather: Visual Crossing Timeline API (keyed, VISUALCROSSING_API_KEY)
    — hourly temperature, feels-like, sea-level pressure, wind, cloud
    cover, precipitation, and an `icon` field ("thunder"-prefixed values
    -> is_storm). The icon alone misses wind-driven storms (verified
    against Hurricane Ian's 2022-09-28 landfall: icon stayed "rain" all
    day despite 113 km/h gusts), so is_storm also fires on windgust
    >=62 km/h (NOAA Gale Warning threshold). No discrete heavy-precip
    code exists in this API, so is_heavy_precip uses a standard
    meteorological heavy-rain threshold (>=7.6mm in the hour) instead.
    15-day horizon.
    If Visual Crossing fails (including after retry/backoff), falls back
    to Open-Meteo (free, no key) — hourly temperature, apparent
    temperature, sea-level pressure, wind, cloud cover, precipitation,
    and weather_code (95/96/99 = thunderstorm -> is_storm). 14-day horizon.
    If Open-Meteo also fails, falls back further to OpenWeatherMap One
    Call 3.0 (keyed, OPENWEATHERMAP_API_KEY). Its free hourly data only
    reaches 48h out, so a forecast served by that last fallback is
    shorter than one served by Visual Crossing or Open-Meteo — no hybrid
    daily-summary fallback for the days-3-14 range in that case.
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

import asyncio
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import ephem
import httpx

from bite_prediction.engine import HourlyConditions

logger = logging.getLogger(__name__)

VISUAL_CROSSING_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
VISUALCROSSING_API_KEY = os.getenv("VISUALCROSSING_API_KEY", "")
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHERMAP_URL = "https://api.openweathermap.org/data/3.0/onecall"
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
NOAA_STATIONS_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    "?type=tidepredictions"
)
NOAA_PREDICTIONS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

MAX_TIDE_STATION_KM = 50.0
_HTTP_TIMEOUT = 10.0
# HF Spaces' shared outbound IPs get intermittently rate-limited/throttled
# by Open-Meteo (the primary feed) — retry a couple of times with backoff
# before falling back to OpenWeatherMap.
_WEATHER_RETRIES = 2
_WEATHER_RETRY_DELAY = 1.5
_STORM_ICON_SUBSTRING = "thunder"  # Visual Crossing icon values: thunder, thunder-rain, thunder-showers-day/night
# NOAA Gale Warning threshold (34kt): verified against Hurricane Ian's 2022-09-28
# landfall data that the "thunder" icon alone never fires for wind-driven storms
# (icon stayed "rain" all day despite 113 km/h gusts) — wind danger needs its own check.
_STORM_WIND_GUST_KMH = 62.0
# Standard meteorological heavy-rain threshold (~0.3 in/hr); Visual Crossing
# has no discrete heavy-precip code like the other two providers.
_HEAVY_PRECIP_MM_PER_HR = 7.6
_STORM_WEATHER_CODES = {95, 96, 99}  # Open-Meteo WMO thunderstorm codes
# WMO heavy-precipitation codes: heavy rain (65), heavy freezing rain (67),
# heavy snow (75), violent rain showers (82), heavy snow showers (86)
_HEAVY_PRECIP_CODES_OM = {65, 67, 75, 82, 86}
_STORM_CODE_MIN, _STORM_CODE_MAX = 200, 232  # OWM thunderstorm group (2xx)
# OWM heavy-precipitation codes: heavy/very heavy/extreme rain (502/503/504),
# freezing rain (511), heavy shower rain (522), heavy snow (602/622)
_HEAVY_PRECIP_CODES_OWM = {502, 503, 504, 511, 522, 602, 622}

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
class CurrentConditions:
    """A nowcast, so a shower happening right now is caught even when the
    hourly forecast missed it."""
    time: datetime      # local naive
    precipitation_mm: float
    is_storm: bool
    is_heavy_precip: bool


@dataclass
class ForecastData:
    conditions: list[HourlyConditions]
    sun_times: list[SunTimes]  # per-day sunrise/sunset (drives the dawn/dusk boost)
    current: CurrentConditions | None


async def fetch_hourly_conditions(lat: float, lon: float, hours: int) -> ForecastData:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            weather = await _fetch_visual_crossing(client, lat, lon)
            build = _build_from_visual_crossing
        except WeatherProviderError as e:
            logger.warning("Visual Crossing unavailable, falling back to Open-Meteo: %s", e)
            try:
                weather = await _fetch_open_meteo(client, lat, lon)
                build = _build_from_open_meteo
            except WeatherProviderError as e:
                logger.warning("Open-Meteo unavailable, falling back to OpenWeatherMap: %s", e)
                weather = await _fetch_openweathermap(client, lat, lon)
                build = _build_from_openweathermap

        # Tides are optional enrichment: any failure means None water fields,
        # which the engine scores as a neutral default.
        try:
            tide_rates = await _fetch_tide_rates(client, lat, lon)
        except Exception:
            tide_rates = {}

    return build(weather, lat, lon, hours, tide_rates)


# --------------------------------------------------------------------------- #
# Visual Crossing (weather — primary)
# --------------------------------------------------------------------------- #

async def _fetch_visual_crossing(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    if not VISUALCROSSING_API_KEY:
        raise WeatherProviderError("VISUALCROSSING_API_KEY is not set")

    url = f"{VISUAL_CROSSING_URL}/{lat},{lon}"
    params = {
        "unitGroup": "metric",
        "include": "hours,current",
        "key": VISUALCROSSING_API_KEY,
        "contentType": "json",
    }
    last_error: httpx.HTTPError | None = None
    for attempt in range(_WEATHER_RETRIES + 1):
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("Visual Crossing request failed (attempt %d/%d): %s",
                            attempt + 1, _WEATHER_RETRIES + 1, e)
            if attempt < _WEATHER_RETRIES:
                await asyncio.sleep(_WEATHER_RETRY_DELAY * (attempt + 1))
    else:
        raise WeatherProviderError(f"Visual Crossing request failed: {last_error}") from last_error

    if "days" not in data:
        raise WeatherProviderError(f"Visual Crossing response missing days data: {data}")
    return data


def _build_from_visual_crossing(
    weather: dict, lat: float, lon: float, hours: int, tide_rates: dict[datetime, float],
) -> ForecastData:
    utc_offset = timedelta(hours=weather["tzoffset"])
    days = weather["days"]

    sun_times = [
        SunTimes(
            date=d["datetime"],
            sunrise=datetime.utcfromtimestamp(d["sunriseEpoch"]) + utc_offset,
            sunset=datetime.utcfromtimestamp(d["sunsetEpoch"]) + utc_offset,
        )
        for d in days
    ]
    sun_by_date = {s.date: (s.sunrise.time(), s.sunset.time()) for s in sun_times}

    hourly = [h for d in days for h in d["hours"]]
    pressures = [h["pressure"] for h in hourly]

    conditions: list[HourlyConditions] = []
    for i, h in enumerate(hourly):
        if len(conditions) >= hours:
            break

        ts_utc = datetime.utcfromtimestamp(h["datetimeEpoch"])
        ts = ts_utc + utc_offset  # local naive
        icon = h.get("icon", "")
        precip = h.get("precip") or 0.0
        windgust = h.get("windgust") or 0.0
        moon = _moon_metrics(lat, lon, ts_utc)
        sunrise, sunset = sun_by_date.get(ts.date().isoformat(), (None, None))

        conditions.append(HourlyConditions(
            timestamp=ts,
            air_temp_c=h["temp"],
            feels_like_c=h["feelslike"],
            pressure_hpa=h["pressure"],
            pressure_delta_3h=pressures[i] - pressures[i - 3] if i >= 3 else 0.0,
            pressure_delta_24h=pressures[i] - pressures[i - 24] if i >= 24 else 0.0,
            wind_speed_kmh=h["windspeed"],  # metric unit group is already km/h
            cloud_cover_pct=h["cloudcover"],
            precip_mm=precip,
            precip_probability_pct=h.get("precipprob", 0.0),
            is_storm=_STORM_ICON_SUBSTRING in icon or windgust >= _STORM_WIND_GUST_KMH,
            is_heavy_precip=precip >= _HEAVY_PRECIP_MM_PER_HR,
            moon_phase=moon["phase"],
            minutes_from_moon_major=moon["minutes_from_major"],
            minutes_from_moon_minor=moon["minutes_from_minor"],
            tide_rate_m_per_hr=tide_rates.get(ts_utc.replace(minute=0)),
            lake_level_trend_cm_per_day=None,  # no lake-level feed yet
            sunrise=sunrise,
            sunset=sunset,
        ))

    current = None
    cur = weather.get("currentConditions")
    if cur:
        icon = cur.get("icon", "")
        precip = cur.get("precip") or 0.0
        windgust = cur.get("windgust") or 0.0
        current = CurrentConditions(
            time=datetime.utcfromtimestamp(cur["datetimeEpoch"]) + utc_offset,
            precipitation_mm=precip,
            is_storm=_STORM_ICON_SUBSTRING in icon or windgust >= _STORM_WIND_GUST_KMH,
            is_heavy_precip=precip >= _HEAVY_PRECIP_MM_PER_HR,
        )

    return ForecastData(conditions=conditions, sun_times=sun_times, current=current)


# --------------------------------------------------------------------------- #
# Open-Meteo (weather — fallback)
# --------------------------------------------------------------------------- #

async def _fetch_open_meteo(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m", "apparent_temperature", "pressure_msl",
            "wind_speed_10m", "cloud_cover", "precipitation",
            "precipitation_probability", "weather_code",
        ]),
        "daily": "sunrise,sunset",
        "current": "weather_code,precipitation",
        "timezone": "auto",
        "past_days": 1,       # history for the 3h/24h pressure deltas
        "forecast_days": 16,  # 14-day horizon regardless of time of day (16 = Open-Meteo max)
    }
    last_error: httpx.HTTPError | None = None
    for attempt in range(_WEATHER_RETRIES + 1):
        try:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("Open-Meteo request failed (attempt %d/%d): %s",
                            attempt + 1, _WEATHER_RETRIES + 1, e)
            if attempt < _WEATHER_RETRIES:
                await asyncio.sleep(_WEATHER_RETRY_DELAY * (attempt + 1))
    else:
        raise WeatherProviderError(f"Open-Meteo request failed: {last_error}") from last_error

    if "hourly" not in data or "daily" not in data:
        raise WeatherProviderError(f"Open-Meteo response missing hourly/daily data: {data}")
    return data


def _build_from_open_meteo(
    weather: dict, lat: float, lon: float, hours: int, tide_rates: dict[datetime, float],
) -> ForecastData:
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
            precip_probability_pct=(hourly.get("precipitation_probability") or [None] * len(timestamps))[i],
            is_storm=hourly["weather_code"][i] in _STORM_WEATHER_CODES,
            is_heavy_precip=hourly["weather_code"][i] in _HEAVY_PRECIP_CODES_OM,
            moon_phase=moon["phase"],
            minutes_from_moon_major=moon["minutes_from_major"],
            minutes_from_moon_minor=moon["minutes_from_minor"],
            tide_rate_m_per_hr=tide_rates.get(ts_utc.replace(minute=0)),
            lake_level_trend_cm_per_day=None,  # no lake-level feed yet
            sunrise=sunrise,
            sunset=sunset,
        ))

    current = None
    cur = weather.get("current")
    if cur and cur.get("weather_code") is not None:
        code = cur["weather_code"]
        current = CurrentConditions(
            time=datetime.fromisoformat(cur["time"]),
            precipitation_mm=cur.get("precipitation") or 0.0,
            is_storm=code in _STORM_WEATHER_CODES,
            is_heavy_precip=code in _HEAVY_PRECIP_CODES_OM,
        )

    return ForecastData(conditions=conditions, sun_times=sun_times, current=current)


# --------------------------------------------------------------------------- #
# OpenWeatherMap (weather — fallback)
# --------------------------------------------------------------------------- #

async def _fetch_openweathermap(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    if not OPENWEATHERMAP_API_KEY:
        raise WeatherProviderError("OPENWEATHERMAP_API_KEY is not set")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric",
        "exclude": "minutely,alerts",
    }
    last_error: httpx.HTTPError | None = None
    for attempt in range(_WEATHER_RETRIES + 1):
        try:
            resp = await client.get(OPENWEATHERMAP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("OpenWeatherMap request failed (attempt %d/%d): %s",
                            attempt + 1, _WEATHER_RETRIES + 1, e)
            if attempt < _WEATHER_RETRIES:
                await asyncio.sleep(_WEATHER_RETRY_DELAY * (attempt + 1))
    else:
        raise WeatherProviderError(f"OpenWeatherMap request failed: {last_error}") from last_error

    if "hourly" not in data or "daily" not in data:
        raise WeatherProviderError(f"OpenWeatherMap response missing hourly/daily data: {data}")
    return data


def _build_from_openweathermap(
    weather: dict, lat: float, lon: float, hours: int, tide_rates: dict[datetime, float],
) -> ForecastData:
    utc_offset = timedelta(seconds=weather["timezone_offset"])

    sun_times = [
        SunTimes(
            date=(datetime.utcfromtimestamp(d["dt"]) + utc_offset).date().isoformat(),
            sunrise=datetime.utcfromtimestamp(d["sunrise"]) + utc_offset,
            sunset=datetime.utcfromtimestamp(d["sunset"]) + utc_offset,
        )
        for d in weather["daily"]
    ]
    sun_by_date = {s.date: (s.sunrise.time(), s.sunset.time()) for s in sun_times}

    hourly = weather["hourly"]
    pressures = [h["pressure"] for h in hourly]

    conditions: list[HourlyConditions] = []
    for i, h in enumerate(hourly):
        if len(conditions) >= hours:
            break

        ts_utc = datetime.utcfromtimestamp(h["dt"])
        ts = ts_utc + utc_offset  # local naive
        code = h["weather"][0]["id"]
        rain_mm = h.get("rain", {}).get("1h", 0.0)
        snow_mm = h.get("snow", {}).get("1h", 0.0)
        moon = _moon_metrics(lat, lon, ts_utc)
        sunrise, sunset = sun_by_date.get(ts.date().isoformat(), (None, None))

        conditions.append(HourlyConditions(
            timestamp=ts,
            air_temp_c=h["temp"],
            feels_like_c=h["feels_like"],
            pressure_hpa=h["pressure"],
            pressure_delta_3h=pressures[i] - pressures[i - 3] if i >= 3 else 0.0,
            pressure_delta_24h=pressures[i] - pressures[i - 24] if i >= 24 else 0.0,
            wind_speed_kmh=h["wind_speed"] * 3.6,  # OWM metric units are m/s
            cloud_cover_pct=h["clouds"],
            precip_mm=rain_mm + snow_mm,
            precip_probability_pct=h.get("pop", 0.0) * 100,
            is_storm=_STORM_CODE_MIN <= code <= _STORM_CODE_MAX,
            is_heavy_precip=code in _HEAVY_PRECIP_CODES_OWM,
            moon_phase=moon["phase"],
            minutes_from_moon_major=moon["minutes_from_major"],
            minutes_from_moon_minor=moon["minutes_from_minor"],
            tide_rate_m_per_hr=tide_rates.get(ts_utc.replace(minute=0)),
            lake_level_trend_cm_per_day=None,  # no lake-level feed yet
            sunrise=sunrise,
            sunset=sunset,
        ))

    current = None
    cur = weather.get("current")
    if cur and cur.get("weather"):
        code = cur["weather"][0]["id"]
        current = CurrentConditions(
            time=datetime.utcfromtimestamp(cur["dt"]) + utc_offset,
            precipitation_mm=cur.get("rain", {}).get("1h", 0.0) + cur.get("snow", {}).get("1h", 0.0),
            is_storm=_STORM_CODE_MIN <= code <= _STORM_CODE_MAX,
            is_heavy_precip=code in _HEAVY_PRECIP_CODES_OWM,
        )

    return ForecastData(conditions=conditions, sun_times=sun_times, current=current)


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
