"""Caleroo web app."""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.estimator import EstimatorError, estimate_calories, estimates_ready, inference_mode, sniff_image, sum_items

logger = logging.getLogger("caleroo")
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_IMAGE_BYTES = 8 * 1024 * 1024

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    db.init()
    logger.info("ready inference=%s model=%s", inference_mode(), db.configured_model() or "unset")
    yield


app = FastAPI(title="Caleroo", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/settings")
def get_settings() -> dict:
    return {
        "daily_goal": db.daily_goal(),
        "model": db.configured_model(),
        "model_is_custom": db.model_is_custom(),
        "inference": inference_mode(),
        "estimates_ready": estimates_ready() and bool(db.configured_model()),
        "api_key_set": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


@app.put("/api/settings")
async def put_settings(request: Request) -> dict:
    data = await _json_object(request)
    if "daily_goal" in data:
        try:
            goal = int(data["daily_goal"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Daily goal must be a whole number.") from None
        if goal < 800 or goal > 8000:
            raise HTTPException(status_code=400, detail="Keep the daily goal between 800 and 8000 kcal.")
        db.set_setting("daily_goal", str(goal))
    if "model" in data:
        model = " ".join(str(data["model"] or "").split())
        if model and not _valid_model(model):
            raise HTTPException(
                status_code=400,
                detail="Use a model name without spaces.",
            )
        db.set_setting("model", model)
    return get_settings()


@app.get("/api/days/{day}")
def get_day(day: str) -> dict:
    parsed = _parse_day(day)
    meals = db.meals_on(parsed.isoformat())
    return {
        "date": parsed.isoformat(),
        "goal": db.daily_goal(),
        "totals": _totals(meals),
        "meals": meals,
    }


@app.get("/api/weeks/{day}")
def get_week(day: str) -> dict:
    parsed = _parse_day(day)
    return {"end": parsed.isoformat(), "goal": db.daily_goal(), "days": db.week_ending(parsed)}


@app.post("/api/analyze")
async def analyze(request: Request) -> dict:
    image, media_type = await _read_upload(request, field="image")
    model = db.configured_model()
    started = time.perf_counter()
    try:
        estimate = await estimate_calories(image, media_type, model=model)
    except EstimatorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info(
        "estimate %.1fs model=%s kcal=%s",
        time.perf_counter() - started,
        model,
        estimate["calories"],
    )
    return estimate


@app.post("/api/meals")
async def create_meal(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    image_bytes = None
    media_type = None
    if "application/json" in content_type:
        data = await _json_object(request)
    else:
        form = await request.form()
        raw = form.get("payload")
        if not isinstance(raw, str) or not raw.strip():
            raise HTTPException(status_code=400, detail="Missing meal details.")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Meal details were not valid JSON.") from None
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Meal details must be an object.")
        upload = form.get("image")
        if upload is not None and hasattr(upload, "read"):
            image_bytes = await upload.read()
            media_type = sniff_image(image_bytes)
            if media_type is None:
                raise HTTPException(status_code=400, detail="Use a JPEG, PNG, WebP, or GIF photo.")
            if len(image_bytes) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="That photo is larger than 8 MB.")
    meal = _meal_from_client(data)
    image_name = None
    if image_bytes is not None and media_type is not None:
        image_name = db.save_image(image_bytes, media_type)
    try:
        return db.insert_meal(meal, image_name)
    except Exception:
        if image_name:
            path = db.data_dir() / "images" / image_name
            if path.is_file():
                path.unlink()
        raise


@app.delete("/api/meals/{meal_id}")
def remove_meal(meal_id: int) -> dict:
    if not db.delete_meal(meal_id):
        raise HTTPException(status_code=404, detail="That meal is no longer in the log.")
    return {"ok": True}


@app.get("/api/meals/{meal_id}/image")
def meal_image(meal_id: int) -> FileResponse:
    path = db.image_path(meal_id)
    if path is None:
        raise HTTPException(status_code=404, detail="This meal has no photo.")
    media = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=86400"})


def _parse_day(value: str) -> date:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Use a YYYY-MM-DD date.") from None
    latest = datetime.now(timezone.utc).date() + timedelta(days=1)
    if parsed.year < 2000 or parsed > latest:
        raise HTTPException(status_code=400, detail="That date is out of range.")
    return parsed


def _valid_model(model: str) -> bool:
    if len(model) > 120 or " " in model:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-")
    return all(char in allowed for char in model)


def _clean(value, limit: int) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:limit]


def _num(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0 or number > 20000:
        return 0.0
    return number


def _items_from_client(raw_items) -> list[dict]:
    if not isinstance(raw_items, list):
        return []
    items = []
    for raw in raw_items[:24]:
        if not isinstance(raw, dict):
            continue
        name = _clean(raw.get("name"), 80)
        if not name:
            continue
        items.append(
            {
                "name": name,
                "portion": _clean(raw.get("portion"), 48),
                "calories": int(round(_num(raw.get("calories")))),
                "protein_g": round(_num(raw.get("protein_g")), 1),
                "carbs_g": round(_num(raw.get("carbs_g")), 1),
                "fat_g": round(_num(raw.get("fat_g")), 1),
            }
        )
    return items


def _meal_from_client(data: dict) -> dict:
    eaten_on = _parse_day(str(data.get("eaten_on") or "")).isoformat()
    items = _items_from_client(data.get("items"))
    notes = _clean(data.get("notes"), 280)
    confidence = data.get("confidence") if data.get("confidence") in {"low", "medium", "high"} else ""
    model = _clean(data.get("model"), 120)
    if model and not _valid_model(model):
        model = ""
    if items:
        title = _clean(data.get("title"), 80) or ", ".join(item["name"] for item in items[:3])
        totals = sum_items(items)
    else:
        title = _clean(data.get("title"), 80)
        if not title:
            raise HTTPException(status_code=400, detail="Name the meal.")
        calories = int(round(_num(data.get("calories"))))
        if calories <= 0:
            raise HTTPException(status_code=400, detail="Enter calories above zero.")
        totals = {
            "calories": calories,
            "protein_g": round(_num(data.get("protein_g")), 1),
            "carbs_g": round(_num(data.get("carbs_g")), 1),
            "fat_g": round(_num(data.get("fat_g")), 1),
        }
        items = [{"name": title, "portion": _clean(data.get("portion"), 48), **totals}]
    return {
        "eaten_on": eaten_on,
        "title": title,
        "notes": notes,
        "confidence": confidence,
        "model": model,
        "items": items,
        **totals,
    }


def _totals(meals: list[dict]) -> dict:
    return {
        "calories": sum(meal["calories"] for meal in meals),
        "protein_g": round(sum(meal["protein_g"] for meal in meals), 1),
        "carbs_g": round(sum(meal["carbs_g"] for meal in meals), 1),
        "fat_g": round(sum(meal["fat_g"] for meal in meals), 1),
    }


async def _json_object(request: Request) -> dict:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Send JSON.") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object.")
    return data


async def _read_upload(request: Request, field: str) -> tuple[bytes, str]:
    form = await request.form()
    upload = form.get(field)
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Choose a photo first.")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="That photo was empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="That photo is larger than 8 MB.")
    media_type = sniff_image(data)
    if media_type is None:
        raise HTTPException(status_code=400, detail="Use a JPEG, PNG, WebP, or GIF photo.")
    return data, media_type
