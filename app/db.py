"""SQLite storage for meals, settings, and optional accounts."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.auth import AVATARS, SESSION_DAYS, check_password


_ready = False
_ready_lock = threading.Lock()
_scope: ContextVar[int | None] = ContextVar("caleroo_user", default=None)


def scope_id() -> int | None:
    return _scope.get()


def set_scope(user_id: int | None):
    return _scope.set(user_id)


def reset_scope(token) -> None:
    _scope.reset(token)


def _user_id() -> int | None:
    user_id = scope_id()
    if user_id is None:
        return None
    return int(user_id)


def _with_user(sql: str, params: list) -> tuple[str, list]:
    """Keep a query on the current account, or on the shared log when nobody is signed in."""
    if " where " not in sql.lower():
        raise RuntimeError("scope filter needs a WHERE clause")
    user_id = _user_id()
    if user_id is None:
        return f"{sql} AND user_id IS NULL", params
    return f"{sql} AND user_id = ?", [*params, user_id]


def _setting_key(key: str) -> str:
    user_id = _user_id()
    if user_id is None:
        return key
    return f"{user_id}:{key}"


IMAGE_SUFFIX = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
THEMES = frozenset({"lime", "dusk", "paper", "ink", "chalk"})


def data_dir() -> Path:
    raw = os.environ.get("DATA_DIR")
    path = Path(raw) if raw else Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "caleroo.sqlite"


def _purge_expired(conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc)
    stale: list[str] = []
    for row in conn.execute("SELECT token_hash, expires_at FROM sessions"):
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            stale.append(row["token_hash"])
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            stale.append(row["token_hash"])
    if stale:
        conn.executemany("DELETE FROM sessions WHERE token_hash = ?", [(item,) for item in stale])


def init() -> None:
    global _ready
    with _ready_lock:
        if _ready:
            return
        (data_dir() / "images").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path(), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
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
                    image_name TEXT,
                    user_id INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_meals_eaten_on ON meals (eaten_on);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    avatar TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(meals)")}
            if "user_id" not in columns:
                conn.execute("ALTER TABLE meals ADD COLUMN user_id INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_meals_user_eaten ON meals (user_id, eaten_on)"
            )
            _purge_expired(conn)
            conn.commit()
        finally:
            conn.close()
        _ready = True


@contextmanager
def connect():
    init()
    conn = sqlite3.connect(db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_setting(key: str) -> str | None:
    scoped = _setting_key(key)
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (scoped,)).fetchone()
    return None if row is None else row["value"]


def set_setting(key: str, value: str) -> None:
    scoped = _setting_key(key)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (scoped, value),
        )


def _clamp(raw: str | None, default: int, low: int, high: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        goal = int(raw)
    except ValueError:
        return default
    return min(max(goal, low), high)


def _read_settings(keys: tuple[str, ...]) -> dict[str, str | None]:
    scoped = [_setting_key(key) for key in keys]
    placeholders = ",".join("?" for _ in scoped)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            scoped,
        ).fetchall()
    found = {row["key"]: row["value"] for row in rows}
    return {key: found.get(_setting_key(key)) for key in keys}


def daily_goal() -> int:
    return _clamp(get_setting("daily_goal"), 2000, 800, 8000)


def macro_goals() -> dict:
    raw = _read_settings(("protein_goal", "carbs_goal", "fat_goal"))
    return {
        "protein_g": _clamp(raw["protein_goal"], 150, 10, 400),
        "carbs_g": _clamp(raw["carbs_goal"], 200, 10, 800),
        "fat_g": _clamp(raw["fat_goal"], 65, 10, 300),
    }


def default_model() -> str:
    from app.estimator import get_provider

    return get_provider().default_model


def configured_model() -> str:
    custom = (get_setting("model") or "").strip()
    if custom:
        return custom
    return default_model()


def model_is_custom() -> bool:
    return bool((get_setting("model") or "").strip())


def theme() -> str:
    raw = (get_setting("theme") or "lime").strip().lower()
    return raw if raw in THEMES else "lime"


def _public_user(row: sqlite3.Row) -> dict:
    avatar = row["avatar"] if row["avatar"] in AVATARS else "lemon"
    return {"id": row["id"], "username": row["username"], "avatar": avatar}


def has_users() -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    return row is not None


def create_user(username: str, password_hash: str, avatar: str) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, avatar, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, avatar, created_at),
            )
            row = conn.execute(
                "SELECT id, username, avatar FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return _public_user(row)
    except sqlite3.IntegrityError:
        raise ValueError("taken") from None


def authenticate(username: str, password: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, username, avatar, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        stored = None if row is None else row["password_hash"]
        public = None if row is None else _public_user(row)
    if not check_password(password, stored) or public is None:
        return None
    return public


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_DAYS)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (_token_hash(token), int(user_id), now.isoformat(), expires.isoformat()),
        )
    return token


def user_from_token(token: str | None) -> dict | None:
    if not token or len(token) > 200:
        return None
    digest = _token_hash(token)
    now = datetime.now(timezone.utc)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT users.id AS id, users.username AS username, users.avatar AS avatar,
                   sessions.expires_at AS expires_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (digest,),
        ).fetchone()
        if row is None:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expires = now
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
            return None
        return _public_user(row)


def delete_session(token: str | None) -> None:
    if not token:
        return
    digest = _token_hash(token[:200])
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))


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
    sql, params = _with_user("SELECT * FROM meals WHERE eaten_on = ?", [day])
    sql += " ORDER BY created_at DESC, id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_meal_from_row(row) for row in rows]


def week_ending(end: date) -> list[dict]:
    start = end - timedelta(days=6)
    sql, params = _with_user(
        """
        SELECT eaten_on,
               COALESCE(SUM(calories), 0) AS calories,
               COALESCE(SUM(protein_g), 0) AS protein_g,
               COALESCE(SUM(carbs_g), 0) AS carbs_g,
               COALESCE(SUM(fat_g), 0) AS fat_g
        FROM meals
        WHERE eaten_on >= ? AND eaten_on <= ?
        """,
        [start.isoformat(), end.isoformat()],
    )
    sql += " GROUP BY eaten_on"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
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


def history() -> dict:
    user_id = _user_id()
    if user_id is None:
        where, params = "WHERE user_id IS NULL", []
    else:
        where, params = "WHERE user_id = ?", [user_id]
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT eaten_on AS day,
                   COALESCE(SUM(calories), 0) AS calories,
                   COALESCE(SUM(protein_g), 0) AS protein_g,
                   COALESCE(SUM(carbs_g), 0) AS carbs_g,
                   COALESCE(SUM(fat_g), 0) AS fat_g,
                   COUNT(*) AS meals
            FROM meals
            {where}
            GROUP BY eaten_on
            ORDER BY eaten_on
            """,
            params,
        ).fetchall()
    days = [
        {
            "date": row["day"],
            "calories": int(row["calories"]),
            "protein_g": round(float(row["protein_g"]), 1),
            "carbs_g": round(float(row["carbs_g"]), 1),
            "fat_g": round(float(row["fat_g"]), 1),
            "meals": int(row["meals"]),
        }
        for row in rows
    ]
    return {
        "first": days[0]["date"] if days else None,
        "goal": daily_goal(),
        "macro_goals": macro_goals(),
        "days": days,
    }


def save_image(data: bytes, media_type: str) -> str:
    suffix = IMAGE_SUFFIX[media_type]
    name = f"{uuid.uuid4().hex}.{suffix}"
    path = data_dir() / "images" / name
    temporary = path.with_name(f".{name}.part")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    except Exception:
        if temporary.is_file():
            temporary.unlink()
        raise
    return name


def _safe_image(name: str | None) -> Path | None:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    path = (data_dir() / "images" / name).resolve()
    root = (data_dir() / "images").resolve()
    if path.parent != root or not path.is_file():
        return None
    return path


def image_path(meal_id: int) -> Path | None:
    sql, params = _with_user("SELECT image_name FROM meals WHERE id = ?", [meal_id])
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return _safe_image(row["image_name"])


def insert_meal(meal: dict, image_name: str | None) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO meals (
                created_at, eaten_on, title, calories, protein_g, carbs_g, fat_g,
                notes, confidence, model, items_json, image_name, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(meal["items"], separators=(",", ":")),
                image_name,
                _user_id(),
            ),
        )
        meal_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
        return _meal_from_row(row)


def delete_meal(meal_id: int) -> bool:
    sql, params = _with_user("SELECT image_name FROM meals WHERE id = ?", [meal_id])
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
        if row is None:
            return False
        image_name = row["image_name"]
        delete_sql, delete_params = _with_user("DELETE FROM meals WHERE id = ?", [meal_id])
        conn.execute(delete_sql, delete_params)
    path = _safe_image(image_name)
    if path is not None:
        try:
            path.unlink()
        except OSError:
            pass
    return True
