"""
Router-level tests — providers are monkeypatched so these never hit the
live government endpoints (mirrors tests/test_predict_api.py's FakePredictor
pattern). Engine parsing itself is covered by test_limits.py/test_consumption.py.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import regs_advisor.router as router_module
from regs_advisor.engine.consumption import SpeciesAdvisoryRecord, Station
from regs_advisor.engine.limits import SpeciesLimit, ZoneLimits
from regs_advisor.engine.zones import ZoneMatch
from regs_advisor.providers.consumption_client import ConsumptionLookupError
from regs_advisor.providers.limits_client import LimitsLookupError
from regs_advisor.providers.llm_client import LLMError
from regs_advisor.providers.zone_client import ZoneLookupError


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


ZONE_27 = ZoneMatch(zone_name="Zone 27", id_zone=31, info_url="https://example.com/zone-27")

WALLEYE_RULE = SpeciesLimit(
    section="Rules for the zone", period="From May 15th to Nov 30th",
    species="Walleye and sauger", catch_limit="6 in all",
    length_limit="37 to 53 cm", fishing_device="Angling only", note=None,
)


def test_limits_returns_zone_rules(client, monkeypatch):
    async def fake_fetch_zone(lat, lon):
        return ZONE_27

    async def fake_fetch_limits(id_zone, zone_name):
        return ZoneLimits(zone_name=zone_name, general_rules=[WALLEYE_RULE], other_sections=[])

    monkeypatch.setattr(router_module, "fetch_zone", fake_fetch_zone)
    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)

    r = client.get("/regs/limits", params={"lat": 46.8, "lon": -71.2})
    assert r.status_code == 200
    body = r.json()
    assert body["zone_name"] == "Zone 27"
    assert len(body["rules"]) == 1
    assert body["rules"][0]["species"] == "Walleye and sauger"


def test_limits_filters_by_species(client, monkeypatch):
    async def fake_fetch_zone(lat, lon):
        return ZONE_27

    async def fake_fetch_limits(id_zone, zone_name):
        return ZoneLimits(zone_name=zone_name, general_rules=[WALLEYE_RULE], other_sections=[])

    monkeypatch.setattr(router_module, "fetch_zone", fake_fetch_zone)
    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)

    r = client.get("/regs/limits", params={"lat": 46.8, "lon": -71.2, "species": "narwhal"})
    assert r.status_code == 404


def test_limits_zone_not_found_returns_404(client, monkeypatch):
    async def fake_fetch_zone(lat, lon):
        raise ZoneLookupError("no fishing zone found")

    monkeypatch.setattr(router_module, "fetch_zone", fake_fetch_zone)

    r = client.get("/regs/limits", params={"lat": 40.0, "lon": -74.0})
    assert r.status_code == 404


def test_limits_provider_down_returns_503(client, monkeypatch):
    async def fake_fetch_zone(lat, lon):
        return ZONE_27

    async def fake_fetch_limits(id_zone, zone_name):
        raise LimitsLookupError("unreachable")

    monkeypatch.setattr(router_module, "fetch_zone", fake_fetch_zone)
    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)

    r = client.get("/regs/limits", params={"lat": 46.8, "lon": -71.2})
    assert r.status_code == 503


PIKE_STATION = Station(no_bqma="05090005", hydronyme="Saint-Charles, Lac", latitude=46.9377, longitude=-71.3866)
PIKE_RECORD = SpeciesAdvisoryRecord(
    no_bqma="05090005", hydronyme="Saint-Charles, Lac", common_name="Grand brochet",
    scientific_name="Esox lucius", english_name="Northern pike", fishing_status="Autorisée",
    meals_per_month=[8, None, None], min_size_cm=[40, 55, 70],
)


def test_consumption_returns_advisory_for_nearest_matching_station(client, monkeypatch):
    async def fake_fetch_nearby_stations(lat, lon):
        return [PIKE_STATION]

    async def fake_fetch_species_record(no_bqma, species_query):
        return [PIKE_RECORD] if "pike" in species_query.lower() else []

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)
    monkeypatch.setattr(router_module, "fetch_species_record", fake_fetch_species_record)

    r = client.get("/regs/consumption", params={"lat": 46.9377, "lon": -71.3866, "species": "pike", "size_cm": 45})
    assert r.status_code == 200
    body = r.json()
    assert body["meals_per_month"] == 8
    assert body["size_class"] == "small"


def test_zones_geojson_returns_provider_data(client, monkeypatch):
    fake_geojson = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"NM_ENDRO_EN": "Zone 27"}}]}

    async def fake_fetch_all_zones_geojson():
        return fake_geojson

    monkeypatch.setattr(router_module, "fetch_all_zones_geojson", fake_fetch_all_zones_geojson)

    r = client.get("/regs/zones/geojson")
    assert r.status_code == 200
    assert r.json() == fake_geojson


def test_zones_geojson_provider_down_returns_503(client, monkeypatch):
    from regs_advisor.providers.zone_client import ZonesGeoJSONError

    async def fake_fetch_all_zones_geojson():
        raise ZonesGeoJSONError("unreachable")

    monkeypatch.setattr(router_module, "fetch_all_zones_geojson", fake_fetch_all_zones_geojson)

    r = client.get("/regs/zones/geojson")
    assert r.status_code == 503


def test_consumption_stations_sorted_by_distance(client, monkeypatch):
    near = Station(no_bqma="1", hydronyme="Near Lake", latitude=46.94, longitude=-71.39)
    far = Station(no_bqma="2", hydronyme="Far Lake", latitude=47.5, longitude=-72.0)

    async def fake_fetch_nearby_stations(lat, lon):
        return [far, near]

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)

    r = client.get("/regs/consumption/stations", params={"lat": 46.9377, "lon": -71.3866})
    assert r.status_code == 200
    body = r.json()
    assert [s["hydronyme"] for s in body] == ["Near Lake", "Far Lake"]
    assert body[0]["distance_km"] < body[1]["distance_km"]


def test_consumption_stations_respects_limit(client, monkeypatch):
    stations = [Station(no_bqma=str(i), hydronyme=f"Lake {i}", latitude=46.9 + i * 0.01, longitude=-71.3) for i in range(5)]

    async def fake_fetch_nearby_stations(lat, lon):
        return stations

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)

    r = client.get("/regs/consumption/stations", params={"lat": 46.9377, "lon": -71.3866, "limit": 2})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_consumption_stations_provider_down_returns_503(client, monkeypatch):
    async def fake_fetch_nearby_stations(lat, lon):
        raise ConsumptionLookupError("unreachable")

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)

    r = client.get("/regs/consumption/stations", params={"lat": 46.9377, "lon": -71.3866})
    assert r.status_code == 503


def test_consumption_no_stations_returns_404(client, monkeypatch):
    async def fake_fetch_nearby_stations(lat, lon):
        return []

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)

    r = client.get("/regs/consumption", params={"lat": 46.9377, "lon": -71.3866, "species": "pike"})
    assert r.status_code == 404


def test_consumption_species_not_at_any_nearby_station_returns_404(client, monkeypatch):
    async def fake_fetch_nearby_stations(lat, lon):
        return [PIKE_STATION]

    async def fake_fetch_species_record(no_bqma, species_query):
        return []

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)
    monkeypatch.setattr(router_module, "fetch_species_record", fake_fetch_species_record)

    r = client.get("/regs/consumption", params={"lat": 46.9377, "lon": -71.3866, "species": "narwhal"})
    assert r.status_code == 404


def test_consumption_provider_down_returns_503(client, monkeypatch):
    async def fake_fetch_nearby_stations(lat, lon):
        raise ConsumptionLookupError("unreachable")

    monkeypatch.setattr(router_module, "fetch_nearby_stations", fake_fetch_nearby_stations)

    r = client.get("/regs/consumption", params={"lat": 46.9377, "lon": -71.3866, "species": "pike"})
    assert r.status_code == 503


# ── /regs/ask — retrieval runs for real (fast, deterministic); only the ──
# ── Claude API call is mocked, so these tests never hit the network.     ──

def test_ask_returns_answer_with_sources(client, monkeypatch):
    def fake_ask_llm(question, context_chunks):
        assert context_chunks  # retrieval found something to ground the answer in
        return "Smallmouth bass respond well to tube jigs on rocky points."

    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "best lure for smallmouth bass"})
    assert r.status_code == 200
    body = r.json()
    assert "tube jigs" in body["answer"]
    assert len(body["sources"]) > 0


def test_ask_injects_live_limits_when_zone_and_species_named(client, monkeypatch):
    async def fake_fetch_limits(id_zone, zone_name):
        assert zone_name == "Zone 8"
        return ZoneLimits(zone_name=zone_name, general_rules=[WALLEYE_RULE], other_sections=[])

    captured = {}

    def fake_ask_llm(question, context_chunks):
        captured["context_chunks"] = context_chunks
        return "In Zone 8, the walleye limit is 6 in all."

    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)
    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "walleye limits in zone 8"})
    assert r.status_code == 200
    body = r.json()
    assert "Zone 8 official limits (live lookup)" in body["sources"]
    assert any("Live official regulations lookup" in c for c in captured["context_chunks"])
    assert any("6 in all" in c for c in captured["context_chunks"])


def test_ask_falls_back_to_kb_when_species_not_in_zone_limits(client, monkeypatch):
    async def fake_fetch_limits(id_zone, zone_name):
        return ZoneLimits(zone_name=zone_name, general_rules=[WALLEYE_RULE], other_sections=[])

    def fake_ask_llm(question, context_chunks):
        assert not any("Live official regulations lookup" in c for c in context_chunks)
        return "No data on that species in this context."

    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)
    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "muskellunge limits in zone 8"})
    assert r.status_code == 200
    assert "Zone 8 official limits (live lookup)" not in r.json()["sources"]


def test_ask_falls_back_to_kb_when_live_limits_provider_down(client, monkeypatch):
    async def fake_fetch_limits(id_zone, zone_name):
        raise LimitsLookupError("unreachable")

    def fake_ask_llm(question, context_chunks):
        return "Falling back to general reference material."

    monkeypatch.setattr(router_module, "fetch_limits", fake_fetch_limits)
    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "walleye limits in zone 8"})
    assert r.status_code == 200
    assert "Zone 8 official limits (live lookup)" not in r.json()["sources"]


def test_ask_no_zone_or_species_named_uses_kb_only(client, monkeypatch):
    def fake_ask_llm(question, context_chunks):
        assert not any("Live official regulations lookup" in c for c in context_chunks)
        return "Smallmouth bass respond well to tube jigs on rocky points."

    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "best lure for smallmouth bass"})
    assert r.status_code == 200


def test_ask_unrelated_question_returns_404(client):
    r = client.post("/regs/ask", json={"question": "xyzzy quantum blockchain nonsense"})
    assert r.status_code == 404


def test_ask_llm_error_returns_503(client, monkeypatch):
    def fake_ask_llm(question, context_chunks):
        raise LLMError("refused")

    monkeypatch.setattr(router_module, "ask_llm", fake_ask_llm)

    r = client.post("/regs/ask", json={"question": "best lure for smallmouth bass"})
    assert r.status_code == 503
