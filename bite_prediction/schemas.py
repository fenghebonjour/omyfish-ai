"""
schemas.py — bite_prediction domain
------------------------------------
Pydantic I/O models only. Kept separate from router.py so the HTTP
contract can be reused (e.g. by a background job or a websocket push)
without importing FastAPI routing machinery.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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


class SpeciesKeyResponse(BaseModel):
    input: str
    species_key: str
    matched: bool
