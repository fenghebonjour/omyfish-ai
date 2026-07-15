"""
router.py — bite_prediction domain
------------------------------------
I/O only. All scoring logic lives in engine/; all provider-fetching
lives in providers/. This file just glues HTTP <-> engine <-> provider.
"""

from fastapi import APIRouter, HTTPException, Query

from bite_prediction.engine import PROFILES, compute_bite_score, best_windows, resolve_species_key
from bite_prediction.providers.weather_client import WeatherProviderError, fetch_hourly_conditions
from bite_prediction.schemas import ForecastResponse, HourlyScoreOut, SpeciesKeyResponse

router = APIRouter(prefix="/bite-score", tags=["bite-score"])


def _to_out(r) -> HourlyScoreOut:
    return HourlyScoreOut(
        timestamp=r.timestamp, score=r.score, breakdown=r.breakdown.as_dict(),
        weighted_contribution=r.weighted_contribution,
        time_of_day_multiplier=r.time_of_day_multiplier, safety_flag=r.safety_flag,
    )


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    lat: float,
    lon: float,
    species: str = Query("general", description="Key from bite_prediction.engine.PROFILES, or a resolvable species name"),
    hours: int = Query(168, le=168, description="Forecast horizon, max 7 days"),
):
    species_key = resolve_species_key(species)
    if species_key is None:
        raise HTTPException(400, f"Unknown species '{species}'. Valid keys: {list(PROFILES)}")

    try:
        conditions = await fetch_hourly_conditions(lat, lon, hours)
    except WeatherProviderError as e:
        raise HTTPException(503, f"Weather provider unavailable: {e}")
    results = [compute_bite_score(c, species_key=species_key) for c in conditions]
    top = best_windows(results, top_n=3, min_gap_hours=3)

    return ForecastResponse(
        species=species_key, lat=lat, lon=lon,
        hourly=[_to_out(r) for r in results],
        best_windows=[_to_out(r) for r in top],
    )


@router.get("/today", response_model=ForecastResponse)
async def get_today(lat: float, lon: float, species: str = "general"):
    """Convenience wrapper the mobile client hits on the home screen."""
    return await get_forecast(lat=lat, lon=lon, species=species, hours=24)


@router.get("/species-key", response_model=SpeciesKeyResponse)
async def get_species_key(name: str = Query(..., description="Common or scientific name, e.g. from a confirmed fish ID")):
    """Resolve a confirmed fish-ID species to the profile key a backend
    should store for that user's future species-tuned forecasts."""
    key = resolve_species_key(name)
    return SpeciesKeyResponse(input=name, species_key=key or "general", matched=key is not None)
