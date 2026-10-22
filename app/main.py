"""Caleroo web app."""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.formparsers import MultiPartException

from app import db
from app.auth import AVATARS, SESSION_COOKIE, SESSION_DAYS, authentication_enabled, hash_password
from app.estimator import (
    EstimatorError,
    advise_rest_of_day,
    close_client,
    configure,
    estimate_calories,
    get_provider,
    open_client,
    sniff_image,
    sum_items,
    unavailable_reason,
)

logger = logging.getLogger("caleroo")
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_BODY_BYTES = 12 * 1024 * 1024
_LOGIN_WINDOW = 600.0
_LOGIN_LIMIT = 8
_login_hits: dict[str, list[float]] = {}
_login_lock = threading.Lock()
_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "script-src 'self' 'sha256-IYBTGH2y6PdjINiXpNJbvpAKWjsccwQdl/dhZDeNkjk='; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    provider = configure()
    db.init()
    await open_client()
    logger.info(
        "ready provider=%s model=%s auth=%s",
        provider.name,
        db.configured_model() or "unset",
        authentication_enabled(),
    )
    try:
        yield
    finally:
        await close_client()


app = FastAPI(title="Caleroo", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _open_path(path: str) -> bool:
    if path == "/" or path.startswith("/static/") or path == "/favicon.ico":
        return True
    return path in {"/api/health", "/api/auth", "/api/register", "/api/login", "/api/logout"}


def _attach_user(request: Request):
    if not authentication_enabled() or request.url.path.startswith("/static/"):
        request.state.user = None
        return db.set_scope(None)
    token = request.cookies.get(SESSION_COOKIE)
    user = db.user_from_token(token) if token else None
    request.state.user = user
    return db.set_scope(user["id"] if user else 0)


def _body_too_large(request: Request) -> bool:
    raw = request.headers.get("content-length")
    if not raw:
        return False
    try:
        size = int(raw)
    except ValueError:
        return False
    return size > MAX_BODY_BYTES


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _login_limited(host: str) -> bool:
    now = time.monotonic()
    with _login_lock:
        recent = [stamp for stamp in _login_hits.get(host, []) if now - stamp < _LOGIN_WINDOW]
        _login_hits[host] = recent
        return len(recent) >= _LOGIN_LIMIT


def _note_login_failure(host: str) -> None:
    now = time.monotonic()
    with _login_lock:
        recent = [stamp for stamp in _login_hits.get(host, []) if now - stamp < _LOGIN_WINDOW]
        recent.append(now)
        _login_hits[host] = recent


def _clear_login_failures(host: str) -> None:
    with _login_lock:
        _login_hits.pop(host, None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    scope_token = _attach_user(request)
    try:
        if _body_too_large(request):
            response = JSONResponse({"detail": "Request is too large."}, status_code=413)
        elif authentication_enabled() and request.state.user is None and not _open_path(request.url.path):
            response = JSONResponse({"detail": "Log in first."}, status_code=401)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        elif request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        db.reset_scope(scope_token)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


def _client_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {"username": user["username"], "avatar": user["avatar"]}


def _auth_body(user: dict | None = None) -> dict:
    enabled = authentication_enabled()
    body = {"authentication": enabled, "user": _client_user(user)}
    if enabled:
        body["avatars"] = list(AVATARS)
        body["has_users"] = db.has_users()
    return body


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https"


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=_cookie_secure(request),
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
    )


def _require_auth_enabled() -> None:
    if not authentication_enabled():
        raise HTTPException(status_code=404, detail="Logins are off.")


def _clean_name(value) -> str:
    return " ".join(str(value or "").split())


def _username(value) -> str:
    name = _clean_name(value)
    if not name:
        raise HTTPException(status_code=400, detail="Enter a name.")
    if len(name) > 24:
        raise HTTPException(status_code=400, detail="Use a name up to 24 characters.")
    if not all(char.isalpha() or char.isdigit() or char in " '-" for char in name):
        raise HTTPException(status_code=400, detail="Use letters and numbers in the name.")
    return name


def _password(value) -> str:
    password = "" if value is None else str(value)
    if len(password) > 200 or len(password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Use a password of at least 6 characters.")
    return password


def _avatar(value) -> str:
    avatar = str(value or "").strip().lower()
    if avatar not in AVATARS:
        raise HTTPException(status_code=400, detail="Pick an avatar.")
    return avatar


@app.get("/api/auth")
def get_auth(request: Request) -> dict:
    return _auth_body(request.state.user)


@app.post("/api/register")
async def register(request: Request, response: Response) -> dict:
    _require_auth_enabled()
    data = await _json_object(request)
    username = _username(data.get("username"))
    password = _password(data.get("password"))
    avatar = _avatar(data.get("avatar"))
    goals = _goal_numbers(data, required=True)
    try:
        user = db.create_user(username, hash_password(password), avatar)
    except ValueError:
        raise HTTPException(status_code=409, detail="That name is taken.") from None
    db.set_scope(user["id"])
    request.state.user = user
    for key, amount in goals.items():
        db.set_setting(key, str(amount))
    _set_session_cookie(response, request, db.create_session(user["id"]))
    return _auth_body(user)


@app.post("/api/login")
async def login(request: Request, response: Response) -> dict:
    _require_auth_enabled()
    host = _client_host(request)
    if _login_limited(host):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a few minutes.")
    data = await _json_object(request)
    user = db.authenticate(
        _clean_name(data.get("username")),
        "" if data.get("password") is None else str(data.get("password")),
    )
    if user is None:
        _note_login_failure(host)
        raise HTTPException(status_code=401, detail="That name or password is wrong.")
    _clear_login_failures(host)
    db.set_scope(user["id"])
    request.state.user = user
    _set_session_cookie(response, request, db.create_session(user["id"]))
    return _auth_body(user)


@app.post("/api/logout")
def logout(request: Request, response: Response) -> dict:
    _require_auth_enabled()
    db.delete_session(request.cookies.get(SESSION_COOKIE))
    _clear_session_cookie(response, request)
    return {"ok": True}


@app.get("/api/settings")
def get_settings(request: Request) -> dict:
    provider = get_provider()
    model = db.configured_model()
    reason = unavailable_reason(model)
    macros = db.macro_goals()
    return {
        "daily_goal": db.daily_goal(),
        "protein_goal": macros["protein_g"],
        "carbs_goal": macros["carbs_g"],
        "fat_goal": macros["fat_g"],
        "model": model,
        "model_is_custom": db.model_is_custom(),
        "default_model": provider.default_model,
        "openrouter": provider.openrouter,
        "estimates_ready": not reason,
        "setup_detail": reason,
        "theme": db.theme(),
        "authentication": authentication_enabled(),
        "user": _client_user(request.state.user),
    }


def _goal_numbers(data: dict, required: bool = False) -> dict:
    if required:
        missing = [key for key in ("daily_goal", "protein_goal", "carbs_goal", "fat_goal") if key not in data]
        if missing:
            raise HTTPException(status_code=400, detail="Set a diet, protein, carbs, and fat goal.")
    goals = {}
    if "daily_goal" in data:
        try:
            goal = int(data["daily_goal"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Daily goal must be a whole number.") from None
        if goal < 800 or goal > 8000:
            raise HTTPException(status_code=400, detail="Keep the daily goal between 800 and 8000 kcal.")
        goals["daily_goal"] = goal
    for key, label, low, high in (
        ("protein_goal", "Protein", 10, 400),
        ("carbs_goal", "Carbs", 10, 800),
        ("fat_goal", "Fat", 10, 300),
    ):
        if key not in data:
            continue
        try:
            amount = int(data[key])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{label} goal must be a whole number.") from None
        if amount < low or amount > high:
            raise HTTPException(
                status_code=400,
                detail=f"Keep the {label.lower()} goal between {low} and {high} g.",
            )
        goals[key] = amount
    return goals


def _store_goals(data: dict) -> None:
    for key, amount in _goal_numbers(data).items():
        db.set_setting(key, str(amount))


@app.put("/api/settings")
async def put_settings(request: Request) -> dict:
    data = await _json_object(request)
    chosen_theme = None
    if "theme" in data:
        chosen_theme = str(data.get("theme") or "").strip().lower()
        if chosen_theme not in db.THEMES:
            raise HTTPException(status_code=400, detail="That theme is not available.")
    _store_goals(data)
    if "model" in data:
        model = " ".join(str(data["model"] or "").split())
        if model and not _valid_model(model):
            raise HTTPException(
                status_code=400,
                detail="Use a model name without spaces.",
            )
        db.set_setting("model", model)
    if chosen_theme is not None:
        db.set_setting("theme", chosen_theme)
    return get_settings(request)


@app.get("/api/days/{day}")
def get_day(day: str) -> dict:
    parsed = _parse_day(day)
    meals = db.meals_on(parsed.isoformat())
    return {
        "date": parsed.isoformat(),
        "goal": db.daily_goal(),
        "macro_goals": db.macro_goals(),
        "totals": _totals(meals),
        "meals": meals,
    }


@app.get("/api/weeks/{day}")
def get_week(day: str) -> dict:
    parsed = _parse_day(day)
    return {
        "end": parsed.isoformat(),
        "goal": db.daily_goal(),
        "macro_goals": db.macro_goals(),
        "days": db.week_ending(parsed),
    }


@app.get("/api/history")
def get_history() -> dict:
    return db.history()


def _require_configured() -> str:
    model = db.configured_model()
    reason = unavailable_reason(model)
    if reason:
        raise HTTPException(
            status_code=503,
            detail=reason,
        )
    return model


@app.post("/api/advice")
async def advice(request: Request) -> dict:
    model = _require_configured()
    data = await _json_object(request)
    day = _parse_day(str(data.get("date") or "")).isoformat()
    local_time = _clean(data.get("local_time"), 32)
    context = _advice_context(day, local_time, _offset_minutes(data.get("timezone_offset_minutes")))
    started = time.perf_counter()
    try:
        result = await advise_rest_of_day(context, model=model)
    except EstimatorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info(
        "advice %.1fs model=%s ideas=%s",
        time.perf_counter() - started,
        model,
        len(result["ideas"]),
    )
    return result


@app.post("/api/analyze")
async def analyze(request: Request) -> dict:
    image, media_type = await _read_upload(request, field="image")
    model = _require_configured()
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
        form = await _form(request)
        try:
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
        finally:
            await form.close()
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
        raise HTTPException(status_code=404, detail="That meal is not in the log.")
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


def _offset_minutes(value) -> int | None:
    try:
        offset = int(value)
    except (TypeError, ValueError):
        return None
    if offset < -840 or offset > 840:
        return None
    return offset


def _grams(value) -> str:
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}"


def _meal_clock(created_at: str, offset: int | None) -> str:
    if offset is None or not created_at:
        return ""
    try:
        stamp = datetime.fromisoformat(created_at)
    except ValueError:
        return ""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    local = stamp - timedelta(minutes=offset)
    hour = local.hour
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{local.minute:02d} {suffix}"


def _macro_status(goals: dict, totals: dict) -> str:
    bits = []
    for key, label in (("protein_g", "protein"), ("carbs_g", "carbs"), ("fat_g", "fat")):
        left = goals[key] - float(totals[key])
        if left >= 0:
            bits.append(f"{label} {_grams(left)} g left")
        else:
            bits.append(f"{label} {_grams(abs(left))} g over")
    return "Macros: " + ", ".join(bits) + "."


def _advice_context(day: str, local_time: str, offset: int | None) -> str:
    meals = list(reversed(db.meals_on(day)))
    totals = _totals(meals)
    goal = db.daily_goal()
    macros = db.macro_goals()
    remaining = goal - totals["calories"]
    if remaining >= 0:
        left = f"{remaining} kcal still available"
    else:
        left = f"{abs(remaining)} kcal over the goal"
    lines = [
        f"Local time: {local_time or 'unknown'}",
        f"Daily calorie goal: {goal}",
        (
            f"Macro goals: protein {macros['protein_g']} g, "
            f"carbs {macros['carbs_g']} g, fat {macros['fat_g']} g"
        ),
        (
            f"Eaten so far: {totals['calories']} kcal "
            f"(protein {_grams(totals['protein_g'])} g, carbs {_grams(totals['carbs_g'])} g, "
            f"fat {_grams(totals['fat_g'])} g)"
        ),
        left,
        _macro_status(macros, totals),
        "",
    ]
    if not meals:
        lines.append("Meals today: none logged yet.")
        return "\n".join(lines)
    lines.append("Meals today:")
    for meal in meals[:16]:
        when = _meal_clock(meal["created_at"], offset)
        prefix = f"{when}, " if when else ""
        names = [
            item.get("name", "")
            for item in (meal.get("items") or [])[:8]
            if isinstance(item, dict) and item.get("name") and item.get("name") != meal["title"]
        ]
        foods = f" Foods: {', '.join(names)}." if names else ""
        lines.append(
            f"- {prefix}{meal['title']}: {meal['calories']} kcal "
            f"(protein {_grams(meal['protein_g'])} g, carbs {_grams(meal['carbs_g'])} g, "
            f"fat {_grams(meal['fat_g'])} g).{foods}"
        )
    return "\n".join(lines)


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


async def _form(request: Request):
    try:
        return await request.form(max_files=2, max_fields=8, max_part_size=MAX_IMAGE_BYTES)
    except MultiPartException:
        raise HTTPException(status_code=413, detail="That upload is larger than 8 MB.") from None


async def _read_upload(request: Request, field: str) -> tuple[bytes, str]:
    form = await _form(request)
    try:
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
    finally:
        await form.close()
