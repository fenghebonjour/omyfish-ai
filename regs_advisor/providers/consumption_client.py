"""
consumption_client.py — regs_advisor.providers
--------------------------------------------------
Wraps the Données Québec "Guide de consommation du poisson" Esri REST
service (confirmed live 2026-07-26, see docs/REGS_CHATBOT_PLAN.md).

Layer 0 = sampling stations (point geometry, no species data).
Layer 1 = one row per species per station, related to layer 0 by
NO_BQMA (esriRelCardinalityOneToOne).

There's no server-side "nearest N stations" query on this service, so
this expands a bounding box around (lat, lon) until stations are found,
then ranks them by haversine distance locally (regs_advisor.engine.consumption).
"""

import httpx

from regs_advisor.engine.consumption import SpeciesAdvisoryRecord, Station

BASE_URL = "https://geo.environnement.gouv.qc.ca/donnees/rest/services/Eau/Guide_poisson/MapServer"
STATIONS_LAYER = f"{BASE_URL}/0/query"
SPECIES_LAYER = f"{BASE_URL}/1/query"
_HTTP_TIMEOUT = 15.0

# Degrees of lat/lon to search, expanding until stations are found.
# ~0.5 deg =~ 55km, 2 deg =~ 220km, 5 deg =~ 550km (covers most of Quebec
# from a single populated area).
_SEARCH_RADII_DEG = (0.5, 2.0, 5.0)


class ConsumptionLookupError(RuntimeError):
    """Raised when the consumption-advisory provider is unreachable."""


async def _query(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ConsumptionLookupError(f"consumption provider unreachable: {e}") from e


async def fetch_nearby_stations(lat: float, lon: float) -> list[Station]:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for radius in _SEARCH_RADII_DEG:
            data = await _query(client, STATIONS_LAYER, {
                "geometry": f"{lon - radius},{lat - radius},{lon + radius},{lat + radius}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "NO_BQMA,HYDRONYME,LATITUDE,LONGITUDE",
                "returnGeometry": "false",
                "f": "json",
            })
            features = data.get("features") or []
            if features:
                return [
                    Station(
                        no_bqma=f["attributes"]["NO_BQMA"],
                        hydronyme=f["attributes"]["HYDRONYME"],
                        latitude=f["attributes"]["LATITUDE"],
                        longitude=f["attributes"]["LONGITUDE"],
                    )
                    for f in features
                    if f["attributes"].get("LATITUDE") is not None
                ]
    return []


async def fetch_species_record(no_bqma: str, species_query: str) -> list[SpeciesAdvisoryRecord]:
    escaped = species_query.replace("'", "''")
    where = (
        f"NO_BQMA='{no_bqma}' AND "
        f"(NOM_ANGLAIS LIKE '%{escaped}%' OR NOM_COMMUN LIKE '%{escaped}%' OR NOM_LATIN LIKE '%{escaped}%')"
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        data = await _query(client, SPECIES_LAYER, {
            "where": where,
            "outFields": (
                "NO_BQMA,HYDRONYME,NOM_COMMUN,NOM_LATIN,NOM_ANGLAIS,STATUT_PECHE,"
                "P_NB_REPAS,M_NB_REPAS,G_NB_REPAS,P_TAILLE_MIN_CM,M_TAILLE_MIN_CM,G_TAILLE_MIN_CM"
            ),
            "returnGeometry": "false",
            "f": "json",
        })

    records = []
    for f in data.get("features") or []:
        a = f["attributes"]
        records.append(SpeciesAdvisoryRecord(
            no_bqma=a["NO_BQMA"],
            hydronyme=a["HYDRONYME"],
            common_name=a["NOM_COMMUN"],
            scientific_name=a["NOM_LATIN"],
            english_name=a["NOM_ANGLAIS"],
            fishing_status=a.get("STATUT_PECHE"),
            meals_per_month=[a.get("P_NB_REPAS"), a.get("M_NB_REPAS"), a.get("G_NB_REPAS")],
            min_size_cm=[a.get("P_TAILLE_MIN_CM"), a.get("M_TAILLE_MIN_CM"), a.get("G_TAILLE_MIN_CM")],
        ))
    return records
