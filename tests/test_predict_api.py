"""/predict endpoint edge cases — fake gate/predictor, no model downloads."""
import base64
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main


def _image_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (16, 16), color=(0, 100, 200)).save(buf, "png")
    return base64.b64encode(buf.getvalue()).decode()


class FakeGate:
    def __init__(self, verdict):
        self.verdict = verdict

    def is_fish(self, image):
        return self.verdict, 0.99 if self.verdict else 0.01


class FakePredictor:
    classes = ["brook_trout", "walleye"]

    def predict(self, image, top_k=5):
        return {
            "predictions": [{"species": "brook_trout", "confidence": 0.87}],
            "uncertain": False,
        }


@pytest.fixture
def client(monkeypatch):
    # Skip real model + CLIP loads at startup; tests inject fakes directly.
    monkeypatch.setenv("DISABLE_FISH_ID", "1")
    monkeypatch.setattr(main, "_predictor", None)
    monkeypatch.setattr(main, "_gate", None)
    monkeypatch.setattr(main, "_metadata", {})
    with TestClient(main.app) as c:
        yield c


def test_predict_rejects_invalid_base64(client):
    r = client.post("/predict", json={"image_base64": "%%%not-base64%%%"})
    assert r.status_code == 400


def test_predict_rejects_non_image_bytes(client):
    payload = base64.b64encode(b"definitely not an image").decode()
    r = client.post("/predict", json={"image_base64": payload})
    assert r.status_code == 400


def test_predict_not_a_fish(client, monkeypatch):
    """Edge case: a cat photo is rejected by the CLIP gate, not classified."""
    monkeypatch.setattr(main, "_gate", FakeGate(False))
    monkeypatch.setattr(main, "_predictor", FakePredictor())
    r = client.post("/predict", json={"image_base64": _image_b64()})
    assert r.status_code == 200
    body = r.json()
    assert body["is_fish"] is False
    assert body["predictions"] == []
    assert body["uncertain"] is True


def test_predict_fish_passes_gate(client, monkeypatch):
    monkeypatch.setattr(main, "_gate", FakeGate(True))
    monkeypatch.setattr(main, "_predictor", FakePredictor())
    r = client.post("/predict", json={"image_base64": _image_b64()})
    body = r.json()
    assert body["is_fish"] is True
    assert body["predictions"][0]["confidence"] == 0.87


def test_predict_stub_mode_when_no_model(client):
    r = client.post("/predict", json={"image_base64": _image_b64()})
    body = r.json()
    assert body["is_fish"] is True
    assert body["uncertain"] is True
    assert [p["rank"] for p in body["predictions"]] == [1, 2]


def test_predict_enriches_from_metadata(client, monkeypatch):
    monkeypatch.setattr(main, "_predictor", FakePredictor())
    monkeypatch.setattr(main, "_metadata", {
        "brook_trout": {
            "species": "Brook Trout",
            "scientific_name": "Salvelinus fontinalis",
            "conservation_status": "Least Concern",
        },
    })
    body = client.post("/predict", json={"image_base64": _image_b64()}).json()
    top = body["predictions"][0]
    assert top["scientific_name"] == "Salvelinus fontinalis"
    assert top["common_name"] == "Brook Trout"
    assert top["conservation_status"] == "Least Concern"


def test_predict_unknown_species_falls_back_to_title_case(client, monkeypatch):
    monkeypatch.setattr(main, "_predictor", FakePredictor())
    body = client.post("/predict", json={"image_base64": _image_b64()}).json()
    top = body["predictions"][0]
    assert top["scientific_name"] == "Brook Trout"
    assert top["common_name"] == "Brook Trout"


def test_health_reports_model_state(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "model_loaded": False}


def test_species_from_predictor_classes(client, monkeypatch):
    monkeypatch.setattr(main, "_predictor", FakePredictor())
    assert client.get("/species").json() == {"species": ["brook_trout", "walleye"]}
