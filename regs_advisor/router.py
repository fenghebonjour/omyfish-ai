"""
router.py — regs_advisor domain
-----------------------------------
I/O + orchestration only. Zone/limits/consumption parsing lives in
engine/; external fetches live in providers/. This file glues
HTTP <-> providers <-> engine, same shape as bite_prediction/router.py.
"""

from fastapi import APIRouter, HTTPException, Query

from regs_advisor.engine.consumption import build_advisory, haversine_km
from regs_advisor.engine.limits import find_species_limit
from regs_advisor.engine.retrieval import get_index
from regs_advisor.providers.consumption_client import (
    ConsumptionLookupError, fetch_nearby_stations, fetch_species_record,
)
from regs_advisor.providers.limits_client import LimitsLookupError, fetch_limits
from regs_advisor.providers.llm_client import LLMError, ask as ask_llm
from regs_advisor.providers.zone_client import (
    ZoneLookupError, ZonesGeoJSONError, fetch_all_zones_geojson, fetch_zone,
)
from regs_advisor.schemas import (
    AskRequest, AskResponse, ConsumptionResponse, LimitsResponse, SpeciesLimitOut, StationOut,
)

router = APIRouter(prefix="/regs", tags=["regs-advisor"])

# How many of the nearest sampling stations to try before giving up on
# finding this species — most species aren't sampled at every station.
_MAX_STATIONS_TRIED = 5


@router.get("/limits", response_model=LimitsResponse)
async def get_limits(
    lat: float,
    lon: float,
    species: str = Query(None, description="Optional species filter, e.g. 'walleye'"),
):
    try:
        zone = await fetch_zone(lat, lon)
    except ZoneLookupError as e:
        raise HTTPException(404, str(e))

    if zone.id_zone is None:
        raise HTTPException(404, f"Zone '{zone.zone_name}' has no known limits-lookup ID")

    try:
        zone_limits = await fetch_limits(zone.id_zone, zone.zone_name)
    except LimitsLookupError as e:
        raise HTTPException(503, str(e))

    rules = zone_limits.general_rules
    if species:
        rules = find_species_limit(zone_limits, species)
        if not rules:
            raise HTTPException(404, f"No limits found for '{species}' in {zone.zone_name}")

    return LimitsResponse(
        lat=lat, lon=lon, zone_name=zone.zone_name, zone_info_url=zone.info_url,
        rules=[SpeciesLimitOut(
            species=r.species, period=r.period, catch_limit=r.catch_limit,
            length_limit=r.length_limit, fishing_device=r.fishing_device, note=r.note,
        ) for r in rules],
    )


@router.get("/zones/geojson")
async def get_zones_geojson():
    """All 34 zone polygons for map overlay — see engine/zones.py, boundaries
    essentially never change so the provider caches this in-process."""
    try:
        return await fetch_all_zones_geojson()
    except ZonesGeoJSONError as e:
        raise HTTPException(503, str(e))


@router.get("/consumption/stations", response_model=list[StationOut])
async def get_consumption_stations(lat: float, lon: float, limit: int = Query(15, ge=1, le=50)):
    """Nearest consumption-advisory sampling sites, for map markers."""
    try:
        stations = await fetch_nearby_stations(lat, lon)
    except ConsumptionLookupError as e:
        raise HTTPException(503, str(e))

    ranked = sorted(stations, key=lambda s: haversine_km(lat, lon, s.latitude, s.longitude))
    return [
        StationOut(
            no_bqma=s.no_bqma, hydronyme=s.hydronyme, latitude=s.latitude, longitude=s.longitude,
            distance_km=round(haversine_km(lat, lon, s.latitude, s.longitude), 1),
        )
        for s in ranked[:limit]
    ]


@router.get("/consumption", response_model=ConsumptionResponse)
async def get_consumption(
    lat: float,
    lon: float,
    species: str = Query(..., description="Species name, e.g. 'walleye' or 'Sander vitreus'"),
    size_cm: float = Query(None, description="Fish length in cm, if known — picks the right size bracket"),
):
    try:
        stations = await fetch_nearby_stations(lat, lon)
    except ConsumptionLookupError as e:
        raise HTTPException(503, str(e))

    if not stations:
        raise HTTPException(404, "No consumption-advisory sampling sites found near this location")

    ranked = sorted(stations, key=lambda s: haversine_km(lat, lon, s.latitude, s.longitude))
    for station in ranked[:_MAX_STATIONS_TRIED]:
        try:
            records = await fetch_species_record(station.no_bqma, species)
        except ConsumptionLookupError as e:
            raise HTTPException(503, str(e))
        if records:
            distance_km = haversine_km(lat, lon, station.latitude, station.longitude)
            advisory = build_advisory(station, distance_km, records[0], size_cm)
            return ConsumptionResponse(
                lat=lat, lon=lon, species=advisory.species, station_name=advisory.station_name,
                distance_km=advisory.distance_km, size_class=advisory.size_class,
                meals_per_month=advisory.meals_per_month, fishing_status=advisory.fishing_status,
                note=advisory.note,
            )

    raise HTTPException(
        404, f"No consumption data for '{species}' at the {len(ranked[:_MAX_STATIONS_TRIED])} nearest sampled sites"
    )


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    chunks = get_index().top_k(request.question, k=4)
    if not chunks:
        raise HTTPException(404, "No reference material matches this question")

    try:
        answer = ask_llm(request.question, [c.text for c, _ in chunks])
    except LLMError as e:
        raise HTTPException(503, str(e))

    return AskResponse(
        question=request.question, answer=answer,
        sources=[c.heading for c, _ in chunks],
    )
