"""
consumption.py — regs_advisor.engine
---------------------------------------
Pure logic for the "Guide de consommation du poisson" (fish-consumption
advisory) dataset — confirmed live Esri REST source, see
docs/REGS_CHATBOT_PLAN.md Phase 0 / the linked memory. Two layers:
layer 0 = sampling stations (lat/lon + waterbody name), layer 1 = one
row per species per station with mercury-driven meals/month advice,
bucketed into small/medium/large size classes (P/M/G in the source
field names — Petit/Moyen/Grand).

A size class's *_NB_REPAS can be null even when its *_TAILLE_MIN_CM is
set (that class wasn't sampled at this station for this species) — the
engine picks the largest qualifying class with a non-null meal count,
never guesses across a gap.
"""

import math
from dataclasses import dataclass
from typing import Optional

EARTH_RADIUS_KM = 6371.0


@dataclass
class Station:
    no_bqma: str
    hydronyme: str  # waterbody name
    latitude: float
    longitude: float


@dataclass
class SpeciesAdvisoryRecord:
    no_bqma: str
    hydronyme: str
    common_name: str
    scientific_name: str
    english_name: str
    fishing_status: Optional[str]
    # index 0/1/2 = small/medium/large (Petit/Moyen/Grand)
    meals_per_month: list[Optional[int]]
    min_size_cm: list[Optional[int]]


@dataclass
class ConsumptionAdvisory:
    station_name: str
    distance_km: float
    species: str
    size_class: Optional[str]       # "small" | "medium" | "large" | None
    meals_per_month: Optional[int]  # None if no size class qualified
    fishing_status: Optional[str]
    note: Optional[str] = None


_SIZE_CLASSES = ["small", "medium", "large"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_station(stations: list[Station], lat: float, lon: float) -> Optional[tuple[Station, float]]:
    if not stations:
        return None
    best = min(stations, key=lambda s: haversine_km(lat, lon, s.latitude, s.longitude))
    return best, haversine_km(lat, lon, best.latitude, best.longitude)


def pick_size_class(record: SpeciesAdvisoryRecord, size_cm: Optional[float]) -> tuple[Optional[str], Optional[int]]:
    """Determine which size class the fish's length actually falls into
    (by threshold alone), then return that class's meal count as-is —
    even if it's null. Never substitutes a smaller class's meal count for
    a larger fish: the source data explicitly warns that contaminant
    levels rise with size, so a smaller class's rule cannot stand in for
    a bigger fish's missing data. Returns (None, None) only when size_cm
    is below every sampled threshold (fish smaller than anything sampled)."""
    if size_cm is None:
        # No fish size given: report the smallest sampled class as the
        # conservative default (lowest meals/month = most restrictive).
        for i in range(len(_SIZE_CLASSES)):
            if record.meals_per_month[i] is not None:
                return _SIZE_CLASSES[i], record.meals_per_month[i]
        return None, None

    for i in reversed(range(len(_SIZE_CLASSES))):
        threshold = record.min_size_cm[i]
        if threshold is not None and size_cm >= threshold:
            return _SIZE_CLASSES[i], record.meals_per_month[i]
    return None, None


def build_advisory(
    station: Station, distance_km: float, record: SpeciesAdvisoryRecord, size_cm: Optional[float],
) -> ConsumptionAdvisory:
    size_class, meals = pick_size_class(record, size_cm)
    note = None
    if size_class is None:
        note = "No consumption data for this size — fish is smaller than the sampled size range at this site."
    elif meals is None:
        note = f"No sampled consumption data for the '{size_class}' size class at this site."
    return ConsumptionAdvisory(
        station_name=station.hydronyme,
        distance_km=round(distance_km, 1),
        species=record.english_name or record.common_name,
        size_class=size_class,
        meals_per_month=meals,
        fishing_status=record.fishing_status,
        note=note,
    )
