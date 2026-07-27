"""
zone_client.py — regs_advisor.providers
------------------------------------------
Point-in-polygon lookup against the official MFFP fishing-zone layer.
Confirmed live, unauthenticated, no API key (see docs/REGS_CHATBOT_PLAN.md
Phase 0). Swap this adapter if the provider ever changes.
"""

import httpx

from regs_advisor.engine.zones import ZoneMatch, resolve_zone_id

ZONES_QUERY_URL = (
    "https://peche.faune.gouv.qc.ca/arcgiswa/rest/services/PRODC-E/"
    "ZonesPecheEn/MapServer/0/query"
)
_HTTP_TIMEOUT = 10.0

# Zone polygons/names essentially never change year to year (see
# engine/zones.py) — cache the full GeoJSON in-process for the life of
# the server instead of re-fetching all 34 zones on every map render.
_zones_geojson_cache: dict | None = None


class ZonesGeoJSONError(RuntimeError):
    """Raised when the zone provider is unreachable for the full-zones fetch."""


async def fetch_all_zones_geojson() -> dict:
    global _zones_geojson_cache
    if _zones_geojson_cache is not None:
        return _zones_geojson_cache

    params = {
        "where": "1=1",
        "outFields": "ID_ZONE,NM_ENDRO_EN,VA_HYPRL_REGLE_EN",
        "outSR": 4326,
        "f": "geojson",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            resp = await client.get(ZONES_QUERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ZonesGeoJSONError(f"zone provider unreachable: {e}") from e

    _zones_geojson_cache = data
    return data


class ZoneLookupError(RuntimeError):
    """Raised when the zone provider is unreachable or returns no match."""


async def fetch_zone(lat: float, lon: float) -> ZoneMatch:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ID_ZONE,NM_ENDRO_EN,VA_HYPRL_REGLE_EN",
        "returnGeometry": "false",
        "f": "json",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            resp = await client.get(ZONES_QUERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ZoneLookupError(f"zone provider unreachable: {e}") from e

    features = data.get("features") or []
    if not features:
        raise ZoneLookupError(f"no fishing zone found for ({lat}, {lon}) — likely outside Quebec")

    attrs = features[0]["attributes"]
    zone_name = attrs.get("NM_ENDRO_EN")
    if not zone_name:
        raise ZoneLookupError(f"zone polygon at ({lat}, {lon}) has no name attribute")

    return ZoneMatch(
        zone_name=zone_name,
        id_zone=resolve_zone_id(zone_name),
        info_url=attrs.get("VA_HYPRL_REGLE_EN"),
    )
