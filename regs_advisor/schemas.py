"""
schemas.py — regs_advisor domain
-----------------------------------
Pydantic I/O models only, kept separate from router.py per the
bite_prediction convention (see bite_prediction/schemas.py).
"""

from typing import Optional

from pydantic import BaseModel


class SpeciesLimitOut(BaseModel):
    species: str
    period: str
    catch_limit: str
    length_limit: Optional[str] = None
    fishing_device: Optional[str] = None
    note: Optional[str] = None


class LimitsResponse(BaseModel):
    lat: float
    lon: float
    zone_name: str
    zone_info_url: Optional[str] = None
    rules: list[SpeciesLimitOut]
    disclaimer: str = "Informational only — verify current regulations at quebec.ca before fishing."


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]  # KB section headings used as context
    disclaimer: str = "Informational only — verify current regulations at quebec.ca before fishing."


class StationOut(BaseModel):
    no_bqma: str
    hydronyme: str
    latitude: float
    longitude: float
    distance_km: float


class ConsumptionResponse(BaseModel):
    lat: float
    lon: float
    species: str
    station_name: str
    distance_km: float
    size_class: Optional[str] = None
    meals_per_month: Optional[int] = None
    fishing_status: Optional[str] = None
    note: Optional[str] = None
    disclaimer: str = "Informational only — based on the nearest sampled site, which may not reflect your exact waterbody."
