"""SQLite storage for meals and settings."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

IMAGE_SUFFIX = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def data_dir() -> Path:
    raw = os.environ.get("DATA_DIR")
    path = Path(raw) if raw else Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "caleroo.sqlite"


_ready = False
_ready_lock = threading.Lock()


def init() -> None:
    global _ready
    with _ready_lock:
        if _ready:
            return
        (data_dir() / "images").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path(), timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    eaten_on TEXT NOT NULL,
                    title TEXT NOT NULL,
                    calories INTEGER NOT NULL,
                    protein_g REAL NOT NULL DEFAULT 0,
                    carbs_g REAL NOT NULL DEFAULT 0,
                    fat_g REAL NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    confidence TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL DEFAULT '[]',
                    image_name TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_meals_eaten_on ON meals (eaten_on);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()
        _ready = True


@contextmanager
def connect():
    init()
    conn = sqlite3.connect(db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_setting(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return None if row is None else row["value"]


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def daily_goal() -> int:
    raw = get_setting("daily_goal") or "2000"
    try:
        goal = int(raw)
    except ValueError:
        return 2000
    return min(max(goal, 800), 8000)


def default_model() -> str:
    if os.environ.get("INFERENCE", "openrouter").strip().lower() == "local":
        return os.environ.get("LOCAL_MODEL", "").strip()
    return os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash").strip() or "google/gemini-2.5-flash"


def configured_model() -> str:
    custom = (get_setting("model") or "").strip()
    if custom:
        return custom
    return default_model()


def model_is_custom() -> bool:
    return bool((get_setting("model") or "").strip())


def _meal_from_row(row: sqlite3.Row) -> dict:
    try:
        items = json.loads(row["items_json"] or "[]")
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "eaten_on": row["eaten_on"],
        "title": row["title"],
        "calories": row["calories"],
        "protein_g": row["protein_g"],
        "carbs_g": row["carbs_g"],
        "fat_g": row["fat_g"],
        "notes": row["notes"],
        "confidence": row["confidence"],
        "model": row["model"],
        "items": items,
        "has_image": bool(row["image_name"]),
    }


def meals_on(day: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE eaten_on = ? ORDER BY created_at DESC, id DESC",
            (day,),
        ).fetchall()
    return [_meal_from_row(row) for row in rows]


def week_ending(end: date) -> list[dict]:
    start = end - timedelta(days=6)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT eaten_on,
                   COALESCE(SUM(calories), 0) AS calories,
                   COALESCE(SUM(protein_g), 0) AS protein_g,
                   COALESCE(SUM(carbs_g), 0) AS carbs_g,
                   COALESCE(SUM(fat_g), 0) AS fat_g
            FROM meals
            WHERE eaten_on >= ? AND eaten_on <= ?
            GROUP BY eaten_on
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    by_day = {row["eaten_on"]: row for row in rows}
    days = []
    for offset in range(7):
        current = start + timedelta(days=offset)
        key = current.isoformat()
        row = by_day.get(key)
        days.append(
            {
                "date": key,
                "calories": int(row["calories"]) if row else 0,
                "protein_g": round(float(row["protein_g"]), 1) if row else 0,
                "carbs_g": round(float(row["carbs_g"]), 1) if row else 0,
                "fat_g": round(float(row["fat_g"]), 1) if row else 0,
            }
        )
    return days


def save_image(data: bytes, media_type: str) -> str:
    suffix = IMAGE_SUFFIX[media_type]
    name = f"{uuid.uuid4().hex}.{suffix}"
    path = data_dir() / "images" / name
    path.write_bytes(data)
    return name


def image_path(meal_id: int) -> Path | None:
    with connect() as conn:
        row = conn.execute("SELECT image_name FROM meals WHERE id = ?", (meal_id,)).fetchone()
    if row is None or not row["image_name"]:
        return None
    name = row["image_name"]
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    path = (data_dir() / "images" / name).resolve()
    if path.parent != (data_dir() / "images").resolve() or not path.is_file():
        return None
    return path


def insert_meal(meal: dict, image_name: str | None) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO meals (
                created_at, eaten_on, title, calories, protein_g, carbs_g, fat_g,
                notes, confidence, model, items_json, image_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                meal["eaten_on"],
                meal["title"],
                meal["calories"],
                meal["protein_g"],
                meal["carbs_g"],
                meal["fat_g"],
                meal["notes"],
                meal["confidence"],
                meal.get("model") or "",
                json.dumps(meal["items"]),
                image_name,
            ),
        )
        meal_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
    return _meal_from_row(row)


def delete_meal(meal_id: int) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT image_name FROM meals WHERE id = ?", (meal_id,)).fetchone()
        if row is None:
            return False
        image_name = row["image_name"]
        conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    if image_name and "/" not in image_name and "\\" not in image_name:
        path = data_dir() / "images" / image_name
        if path.is_file():
            path.unlink()
    return True
