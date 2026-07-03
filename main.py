import base64
import json
import os
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

app = FastAPI(title="OMyFish AI Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL_PATH = os.getenv("MODEL_PATH", "/checkpoints/best.pt")
CLASSES_PATH = os.getenv("CLASSES_PATH", "/checkpoints/classes.json")
METADATA_PATH = os.getenv("METADATA_PATH", "/metadata/fish_info.json")

_predictor = None
_metadata: dict = {}


def _load_metadata() -> dict:
    try:
        entries = json.loads(open(METADATA_PATH).read())
        return {e["species"].lower().replace(" ", "_").replace("-", "_"): e for e in entries}
    except Exception:
        return {}


@app.on_event("startup")
async def startup():
    global _predictor, _metadata
    _metadata = _load_metadata()
    try:
        from predictors.efficientnet import FishPredictor
        _predictor = FishPredictor(MODEL_PATH, CLASSES_PATH)
        print(f"EfficientNet model loaded from {MODEL_PATH}")
    except Exception as e:
        print(f"Model not loaded (stub mode active): {e}")


class PredictRequest(BaseModel):
    image_base64: str
    top_k: int = 5


class Prediction(BaseModel):
    scientific_name: str
    common_name: str
    confidence: float
    rank: int
    conservation_status: Optional[str] = None
    habitat: Optional[str] = None
    diet: Optional[str] = None
    max_size_cm: Optional[int] = None
    description: Optional[str] = None
    fun_fact: Optional[str] = None


class PredictResponse(BaseModel):
    predictions: List[Prediction]
    uncertain: bool


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    try:
        image_bytes = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")

    if _predictor is None:
        return PredictResponse(
            predictions=[
                Prediction(scientific_name="Micropterus salmoides", common_name="Largemouth Bass",
                           confidence=0.42, rank=1),
                Prediction(scientific_name="Micropterus dolomieu", common_name="Smallmouth Bass",
                           confidence=0.28, rank=2),
            ],
            uncertain=True,
        )

    result = _predictor.predict(image, top_k=request.top_k)
    predictions = []
    for i, p in enumerate(result["predictions"], start=1):
        key = p["species"].lower().replace(" ", "_").replace("-", "_")
        meta = _metadata.get(key, {})
        scientific = meta.get("scientific_name", p["species"].replace("_", " ").title())
        common = meta.get("species", p["species"].replace("_", " ").title())
        predictions.append(Prediction(
            scientific_name=scientific,
            common_name=common,
            confidence=p["confidence"],
            rank=i,
            conservation_status=meta.get("conservation_status"),
            habitat=meta.get("habitat"),
            diet=meta.get("diet"),
            max_size_cm=meta.get("max_size_cm"),
            description=meta.get("description"),
            fun_fact=meta.get("fun_fact"),
        ))
    return PredictResponse(predictions=predictions, uncertain=result["uncertain"])


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": _predictor is not None}


@app.get("/species")
async def species():
    if _predictor is not None and hasattr(_predictor, "classes"):
        return {"species": _predictor.classes}
    if _metadata:
        return {"species": list(_metadata.keys())}
    return {"species": []}
