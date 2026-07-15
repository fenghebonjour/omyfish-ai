"""
api.py
------
FastAPI routes wiring the Bite Score engine into omyfish-ai.

This layer owns I/O only: fetching weather/tide data and shaping the
response. All scoring logic lives in bite_score.py so it stays testable
without a live API key and swappable if the weather provider changes.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from bite_score import HourlyConditions, compute_bite_score, best_windows
from species_profiles import PROFILES

router = APIRouter(prefix="/bite-score", tags=["bite-score"])


class HourlyScoreOut(BaseModel):
    timestamp: datetime
    score: float
    breakdown: dict
    weighted_contribution: dict
    time_of_day_multiplier: float
    safety_flag: Optional[str] = None


class ForecastResponse(BaseModel):
    species: str
    lat: float
    lon: float
    hourly: list[HourlyScoreOut]
    best_windows: list[HourlyScoreOut]


async def fetch_hourly_conditions(lat: float, lon: float, hours: int) -> list[HourlyConditions]:
    """
    Adapter boundary: swap this out for the real provider integration
    (e.g. a marine/weather API for wind, pressure, cloud cover, and a
    tide/reservoir-level API for `tide_rate_m_per_hr` or
    `lake_level_trend_cm_per_day`). Keeping this as a single async
    function means the scoring code never needs to know which vendor
    is behind it, and it's the one function integration tests mock.
    """
    raise NotImplementedError(
        "Wire this to the chosen weather + tide/water-level providers; "
        "return one HourlyConditions per forecast hour."
    )


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    lat: float,
    lon: float,
    species: str = Query("general", description="Key from species_profiles.PROFILES"),
    hours: int = Query(168, le=168, description="Forecast horizon, max 7 days"),
):
    if species not in PROFILES:
        raise HTTPException(400, f"Unknown species '{species}'. Valid: {list(PROFILES)}")

    conditions = await fetch_hourly_conditions(lat, lon, hours)
    results = [compute_bite_score(c, species_key=species) for c in conditions]
    top = best_windows(results, top_n=3, min_gap_hours=3)

    to_out = lambda r: HourlyScoreOut(
        timestamp=r.timestamp, score=r.score, breakdown=r.breakdown.as_dict(),
        weighted_contribution=r.weighted_contribution,
        time_of_day_multiplier=r.time_of_day_multiplier, safety_flag=r.safety_flag,
    )

    return ForecastResponse(
        species=species, lat=lat, lon=lon,
        hourly=[to_out(r) for r in results],
        best_windows=[to_out(r) for r in top],
    )


@router.get("/today", response_model=ForecastResponse)
async def get_today(lat: float, lon: float, species: str = "general"):
    """Convenience wrapper the mobile client hits on the home screen."""
    return await get_forecast(lat=lat, lon=lon, species=species, hours=24)
