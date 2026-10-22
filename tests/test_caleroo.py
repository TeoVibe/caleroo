"""Provider config, model replies, and the settings API."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import httpx

TMP = tempfile.mkdtemp(prefix="caleroo-test-")
os.environ["DATA_DIR"] = TMP
os.environ["BASE_URL"] = ""
os.environ["API_KEY"] = "test-key"
os.environ["MODEL"] = ""
os.environ["APP_URL"] = "http://localhost:6969"

from app.estimator import (  # noqa: E402
    EstimatorError,
    advise_rest_of_day,
    bind_client,
    close_client,
    configure,
    estimate_calories,
    extract_json,
    load_provider,
    normalize_estimate,
)
from app.main import _advice_context, app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


PLATE = {
    "title": "Soup",
    "items": [
        {
            "name": "Soup",
            "portion": "1 bowl",
            "calories": 180,
            "protein_g": 6,
            "carbs_g": 20,
            "fat_g": 4,
        }
    ],
    "notes": "assumed a bowl",
    "confidence": "medium",
}


def _reply(payload: dict, status: int = 200) -> httpx.Response:
    body = {"choices": [{"message": {"content": json.dumps(payload)}}]}
    return httpx.Response(status, json=body)


class ProviderTests(unittest.TestCase):
    def test_empty_base_url_is_openrouter(self):
        provider = load_provider({"API_KEY": "k"})
        self.assertTrue(provider.openrouter)
        self.assertEqual(provider.chat_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(provider.default_model, "google/gemini-2.5-flash")
        self.assertEqual(provider.problem, "")
        self.assertEqual(provider.headers()["X-Title"], "Caleroo")

    def test_openrouter_requires_a_key(self):
        provider = load_provider({})
        self.assertEqual(provider.problem, "Set API_KEY before using the model.")
        self.assertTrue(provider.blocking_problem("google/gemini-2.5-flash"))

    def test_explicit_openrouter_url(self):
        provider = load_provider(
            {"BASE_URL": "https://openrouter.ai/api/v1/", "API_KEY": "k", "MODEL": "custom/model"}
        )
        self.assertTrue(provider.openrouter)
        self.assertEqual(provider.default_model, "custom/model")
        self.assertEqual(provider.chat_url, "https://openrouter.ai/api/v1/chat/completions")

    def test_lookalike_host_is_not_openrouter(self):
        provider = load_provider({"BASE_URL": "https://openrouter.ai.evil.test/v1", "MODEL": "vision"})
        self.assertFalse(provider.openrouter)
        self.assertEqual(provider.problem, "")
        self.assertNotIn("X-Title", provider.headers())

    def test_own_server_needs_a_model_not_a_key(self):
        provider = load_provider({"BASE_URL": "http://127.0.0.1:8000/v1"})
        self.assertFalse(provider.openrouter)
        self.assertEqual(provider.problem, "")
        self.assertIn("MODEL", provider.blocking_problem(""))
        ready = load_provider({"BASE_URL": "http://127.0.0.1:8000/v1/", "MODEL": "vision", "API_KEY": ""})
        self.assertEqual(ready.blocking_problem("vision"), "")
        self.assertEqual(ready.chat_url, "http://127.0.0.1:8000/v1/chat/completions")
        self.assertNotIn("Authorization", ready.headers())

    def test_full_completions_url_is_kept(self):
        provider = load_provider(
            {"BASE_URL": "http://127.0.0.1:8000/v1/chat/completions", "MODEL": "vision"}
        )
        self.assertEqual(provider.chat_url, "http://127.0.0.1:8000/v1/chat/completions")

    def test_bad_scheme(self):
        provider = load_provider({"BASE_URL": "ftp://files.example/v1", "MODEL": "vision"})
        self.assertIn("http://", provider.problem)


class ReplyTests(unittest.TestCase):
    def test_fenced_json(self):
        parsed = extract_json('```json\n{"title": "Toast"}\n```')
        self.assertEqual(parsed["title"], "Toast")

    def test_json_with_prose_around_it(self):
        parsed = extract_json('Sure. {"title": "Toast", "items": []} thanks')
        self.assertEqual(parsed["title"], "Toast")

    def test_invalid_json(self):
        with self.assertRaises(EstimatorError):
            extract_json("no json here")

    def test_normalize_drops_bad_items_and_clamps(self):
        estimate = normalize_estimate(
            {
                "title": "",
                "items": [
                    {"name": "Toast", "calories": -5, "protein_g": 3, "carbs_g": 20, "fat_g": 2},
                    {"name": "", "calories": 100},
                    "nope",
                    {"name": "Jam", "calories": 90000, "protein_g": "a"},
                ],
                "confidence": "nope",
            }
        )
        self.assertEqual(estimate["title"], "Toast, Jam")
        self.assertEqual(estimate["calories"], 0)
        self.assertEqual(estimate["confidence"], "medium")
        self.assertEqual(len(estimate["items"]), 2)


class CompleteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        await close_client()

    def _bind(self, handler):
        configure({"API_KEY": "k", "APP_URL": "http://localhost:6969"})
        bind_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def test_retries_once_when_json_mode_is_rejected(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            seen.append(body)
            self.assertEqual(request.headers["authorization"], "Bearer k")
            self.assertEqual(request.headers["x-title"], "Caleroo")
            self.assertTrue(str(request.url).endswith("/chat/completions"))
            if "response_format" in body:
                return httpx.Response(400, json={"error": {"message": "unsupported"}})
            return _reply(PLATE)

        self._bind(handler)
        estimate = await estimate_calories(b"\xff\xd8\xff", "image/jpeg", model="google/gemini-2.5-flash")
        self.assertEqual(estimate["calories"], 180)
        self.assertEqual(estimate["model"], "google/gemini-2.5-flash")
        self.assertEqual(len(seen), 2)
        self.assertNotIn("response_format", seen[1])
        image = seen[1]["messages"][1]["content"][1]["image_url"]["url"]
        self.assertTrue(image.startswith("data:image/jpeg;base64,"))

    async def test_auth_failure_is_not_retried(self):
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(401, json={"error": {"message": "bad"}})

        self._bind(handler)
        with self.assertRaises(EstimatorError) as caught:
            await estimate_calories(b"\xff\xd8\xff", "image/jpeg", model="google/gemini-2.5-flash")
        self.assertEqual(str(caught.exception), "OpenRouter rejected the API key.")
        self.assertEqual(calls, 1)

    async def test_openrouter_out_of_credit(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(402, json={"error": {"message": "credits"}})

        self._bind(handler)
        with self.assertRaisesRegex(EstimatorError, "no credit"):
            await advise_rest_of_day("goal 2000", model="google/gemini-2.5-flash")

    async def test_timeout_and_unreachable(self):
        def timeout(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

        self._bind(timeout)
        with self.assertRaisesRegex(EstimatorError, "too long"):
            await advise_rest_of_day("goal 2000", model="google/gemini-2.5-flash")

        def down(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("nope")

        self._bind(down)
        with self.assertRaisesRegex(EstimatorError, "OpenRouter"):
            await advise_rest_of_day("goal 2000", model="google/gemini-2.5-flash")

    async def test_own_server_omits_the_key_and_names_base_url(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("x-title", request.headers)
            raise httpx.ConnectError("down")

        configure({"BASE_URL": "http://127.0.0.1:8000/v1", "MODEL": "vision", "API_KEY": ""})
        bind_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with self.assertRaisesRegex(EstimatorError, "BASE_URL"):
            await advise_rest_of_day("goal 2000", model="vision")

    async def test_empty_reply(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]})

        self._bind(handler)
        with self.assertRaisesRegex(EstimatorError, "empty reply"):
            await advise_rest_of_day("goal 2000", model="google/gemini-2.5-flash")

    async def test_list_content(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": json.dumps({"summary": "Stop there.", "ideas": []})}
                                ]
                            }
                        }
                    ]
                },
            )

        self._bind(handler)
        advice = await advise_rest_of_day("goal 2000", model="google/gemini-2.5-flash")
        self.assertEqual(advice["summary"], "Stop there.")


class WebTests(unittest.TestCase):
    def _env(self, **values: str) -> None:
        os.environ["BASE_URL"] = values.get("BASE_URL", "")
        os.environ["API_KEY"] = values.get("API_KEY", "test-key")
        os.environ["MODEL"] = values.get("MODEL", "")
        os.environ["APP_URL"] = "http://localhost:6969"
        os.environ["DATA_DIR"] = TMP
        os.environ["AUTHENTICATION"] = values.get("AUTHENTICATION", "false")

    def test_settings_use_openrouter_by_default(self):
        self._env()
        with TestClient(app) as client:
            client.put("/api/settings", json={"model": ""})
            body = client.get("/api/settings").json()
            page = client.get("/").text
        self.assertTrue(body["estimates_ready"])
        self.assertTrue(body["openrouter"])
        self.assertEqual(body["model"], "google/gemini-2.5-flash")
        self.assertEqual(body["default_model"], "google/gemini-2.5-flash")
        self.assertEqual(body["setup_detail"], "")
        self.assertEqual(body["theme"], "lime")
        self.assertNotIn("inference", body)
        self.assertNotIn("Set API_KEY", page)
        self.assertNotIn("by hand", page)
        self.assertNotIn("INFERENCE", page)
        self.assertNotIn("OPENROUTER_API_KEY", page)

    def test_missing_key_blocks_estimates_and_keeps_photo_checks(self):
        self._env(API_KEY="")
        with TestClient(app) as client:
            settings = client.get("/api/settings").json()
            bad = client.post("/api/analyze", files={"image": ("meal.txt", b"hello", "text/plain")})
            photo = client.post(
                "/api/analyze",
                files={"image": ("meal.jpg", b"\xff\xd8\xff\x00", "image/jpeg")},
            )
            advice = client.post("/api/advice", json={"date": "2026-10-19"})
        self.assertFalse(settings["estimates_ready"])
        self.assertIn("API_KEY", settings["setup_detail"])
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(photo.status_code, 503)
        self.assertIn("API_KEY", photo.json()["detail"])
        self.assertNotIn("by hand", photo.json()["detail"])
        self.assertEqual(advice.status_code, 503)

    def test_own_server_is_ready_with_a_model_and_no_key(self):
        self._env(BASE_URL="http://127.0.0.1:8000/v1", API_KEY="", MODEL="vision")
        with TestClient(app) as client:
            client.put("/api/settings", json={"model": ""})
            body = client.get("/api/settings").json()
        self.assertFalse(body["openrouter"])
        self.assertTrue(body["estimates_ready"])
        self.assertEqual(body["model"], "vision")

    def test_own_server_without_a_model_stays_off(self):
        self._env(BASE_URL="http://127.0.0.1:8000/v1", API_KEY="", MODEL="")
        with TestClient(app) as client:
            client.put("/api/settings", json={"model": ""})
            body = client.get("/api/settings").json()
        self.assertFalse(body["estimates_ready"])
        self.assertIn("MODEL", body["setup_detail"])

    def test_health(self):
        self._env()
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").json(), {"ok": True})

    def test_history_groups_days_from_the_first_meal(self):
        self._env()
        with TestClient(app) as client:
            empty = client.get("/api/history").json()
            client.post("/api/meals", json={"eaten_on": "2026-10-18", "title": "Soup", "calories": 180})
            client.post("/api/meals", json={"eaten_on": "2026-10-02", "title": "Toast", "calories": 200})
            client.post("/api/meals", json={"eaten_on": "2026-10-02", "title": "Eggs", "calories": 150})
            body = client.get("/api/history").json()
        self.assertIsNone(empty["first"])
        self.assertEqual(empty["days"], [])
        self.assertEqual(body["first"], "2026-10-02")
        self.assertEqual(body["goal"], 2000)
        self.assertEqual(
            [(day["date"], day["calories"], day["meals"]) for day in body["days"]],
            [("2026-10-02", 350, 2), ("2026-10-18", 180, 1)],
        )

    def test_theme_round_trip(self):
        self._env()
        with TestClient(app) as client:
            bad = client.put("/api/settings", json={"theme": "glare", "daily_goal": 2200})
            kept = client.get("/api/settings").json()
            saved = client.put("/api/settings", json={"theme": "Ink"}).json()
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(kept["theme"], "lime")
        self.assertEqual(kept["daily_goal"], 2000)
        self.assertEqual(saved["theme"], "ink")

    def test_page_has_calendar_and_themes(self):
        self._env()
        with TestClient(app) as client:
            page = client.get("/").text
        self.assertIn("calendar-dialog", page)
        self.assertIn("theme-picker", page)
        self.assertIn("caleroo-theme", page)
        self.assertIn("protein-goal-input", page)
        self.assertIn("carbs-goal-input", page)
        self.assertIn("fat-goal-input", page)
        self.assertIn("ring-protein", page)
        self.assertIn("ring-carbs", page)
        self.assertIn("ring-fat", page)
        self.assertIn("register-form", page)
        self.assertIn("avatar-picker", page)
        self.assertNotIn("open-workout", page)
        self.assertNotIn("workout-dialog", page)

    def test_macro_goals_show_up_with_the_day(self):
        self._env()
        from app import db

        meal_id = None
        try:
            with TestClient(app) as client:
                bad = client.put("/api/settings", json={"protein_goal": 2, "carbs_goal": "nope", "fat_goal": 900})
                kept = client.get("/api/settings").json()
                saved = client.put(
                    "/api/settings",
                    json={"protein_goal": 160, "carbs_goal": 180, "fat_goal": 50},
                ).json()
                meal = client.post(
                    "/api/meals",
                    json={
                        "eaten_on": "2026-09-11",
                        "title": "Rice",
                        "calories": 900,
                        "protein_g": 30,
                        "carbs_g": 40,
                        "fat_g": 10,
                    },
                )
                meal_id = meal.json()["id"]
                day = client.get("/api/days/2026-09-11").json()
                week = client.get("/api/weeks/2026-09-11").json()
                gone = client.post("/api/workouts", json={"done_on": "2026-09-11", "calories": 200})
            self.assertEqual(bad.status_code, 400)
            self.assertEqual(kept["daily_goal"], 2000)
            self.assertEqual(kept["protein_goal"], 150)
            self.assertEqual(kept["carbs_goal"], 200)
            self.assertEqual(kept["fat_goal"], 65)
            self.assertEqual(saved["protein_goal"], 160)
            self.assertEqual(saved["carbs_goal"], 180)
            self.assertEqual(saved["fat_goal"], 50)
            self.assertEqual(saved["daily_goal"], 2000)
            self.assertEqual(day["goal"], 2000)
            self.assertEqual(day["macro_goals"], {"protein_g": 160, "carbs_g": 180, "fat_g": 50})
            self.assertEqual(day["totals"]["calories"], 900)
            self.assertEqual(day["totals"]["protein_g"], 30)
            self.assertEqual(day["totals"]["carbs_g"], 40)
            self.assertEqual(day["totals"]["fat_g"], 10)
            self.assertNotIn("workouts", day)
            self.assertNotIn("burned", day)
            self.assertEqual(week["macro_goals"], day["macro_goals"])
            self.assertNotIn("workout_goal", week)
            logged = next(item for item in week["days"] if item["date"] == "2026-09-11")
            self.assertEqual((logged["protein_g"], logged["carbs_g"], logged["fat_g"]), (30, 40, 10))
            self.assertNotIn("burned", logged)
            self.assertEqual(gone.status_code, 404)
        finally:
            if meal_id is not None:
                db.delete_meal(meal_id)
            with db.connect() as conn:
                conn.execute(
                    "DELETE FROM settings WHERE key IN ('protein_goal', 'carbs_goal', 'fat_goal')"
                )

    def test_advice_context_includes_macro_goals(self):
        self._env()
        from app import db

        previous = db.get_setting("daily_goal")
        db.set_setting("daily_goal", "2000")
        db.set_setting("protein_goal", "150")
        db.set_setting("carbs_goal", "200")
        db.set_setting("fat_goal", "65")
        meal_id = None
        try:
            with TestClient(app) as client:
                meal = client.post(
                    "/api/meals",
                    json={
                        "eaten_on": "2026-08-20",
                        "title": "Toast",
                        "calories": 400,
                        "protein_g": 12,
                        "carbs_g": 40,
                        "fat_g": 8,
                    },
                )
                meal_id = meal.json()["id"]
                text = _advice_context("2026-08-20", "1:00 PM", 0)
            self.assertIn("Macro goals: protein 150 g, carbs 200 g, fat 65 g", text)
            self.assertIn("1600 kcal still available", text)
            self.assertIn("protein 138 g left", text)
            self.assertIn("carbs 160 g left", text)
            self.assertIn("fat 57 g left", text)
            self.assertNotIn("burned", text)
            self.assertNotIn("Workout", text)
        finally:
            if meal_id is not None:
                db.delete_meal(meal_id)
            if previous is None:
                with db.connect() as conn:
                    conn.execute("DELETE FROM settings WHERE key = ?", ("daily_goal",))
            else:
                db.set_setting("daily_goal", previous)
            with db.connect() as conn:
                conn.execute(
                    "DELETE FROM settings WHERE key IN ('protein_goal', 'carbs_goal', 'fat_goal')"
                )

    def test_accounts_are_optional_and_keep_separate_logs(self):
        self._env()
        from app import db

        legacy_id = None
        ada_ids = []
        try:
            with TestClient(app) as shared:
                off = shared.get("/api/auth").json()
                blocked = shared.post("/api/register", json={"username": "Ada", "password": "secret1"})
                legacy = shared.post(
                    "/api/meals",
                    json={"eaten_on": "2026-07-04", "title": "Shared", "calories": 50},
                )
                legacy_id = legacy.json()["id"]
            self.assertFalse(off["authentication"])
            self.assertIsNone(off["user"])
            self.assertNotIn("avatars", off)
            self.assertEqual(blocked.status_code, 404)

            os.environ["AUTHENTICATION"] = "true"
            goals = {
                "daily_goal": 2000,
                "protein_goal": 150,
                "carbs_goal": 200,
                "fat_goal": 65,
            }
            with TestClient(app) as anon, TestClient(app) as ada, TestClient(app) as bo:
                opening = anon.get("/api/auth").json()
                locked = anon.get("/api/days/2026-07-04")
                health = anon.get("/api/health")
                short = anon.post(
                    "/api/register",
                    json={"username": "Ada", "password": "no", "avatar": "lemon", **goals},
                )
                bad_face = anon.post(
                    "/api/register",
                    json={"username": "Ada", "password": "secret1", "avatar": "wizard", **goals},
                )
                created = ada.post(
                    "/api/register",
                    json={
                        "username": "Ada",
                        "password": "secret1",
                        "avatar": "fox",
                        "daily_goal": 1800,
                        "protein_goal": 120,
                        "carbs_goal": 160,
                        "fat_goal": 50,
                    },
                )
                duplicate = anon.post(
                    "/api/register",
                    json={"username": "ada", "password": "secret1", "avatar": "cat", **goals},
                )
                other = bo.post(
                    "/api/register",
                    json={
                        "username": "Bo",
                        "password": "secret2",
                        "avatar": "panda",
                        "daily_goal": 2200,
                        "protein_goal": 160,
                        "carbs_goal": 210,
                        "fat_goal": 70,
                    },
                )
                ada_meal = ada.post(
                    "/api/meals",
                    json={"eaten_on": "2026-07-04", "title": "Ada rice", "calories": 300, "protein_g": 10},
                )
                photo = ada.post(
                    "/api/meals",
                    data={
                        "payload": json.dumps(
                            {
                                "eaten_on": "2026-07-04",
                                "title": "Ada plate",
                                "calories": 100,
                                "protein_g": 5,
                            }
                        )
                    },
                    files={"image": ("meal.jpg", b"\xff\xd8\xff\x00", "image/jpeg")},
                )
                if ada_meal.status_code == 200:
                    ada_ids.append(ada_meal.json()["id"])
                if photo.status_code == 200:
                    ada_ids.append(photo.json()["id"])
                ada_day = ada.get("/api/days/2026-07-04").json()
                bo_day = bo.get("/api/days/2026-07-04").json()
                ada_settings = ada.get("/api/settings").json()
                bo_settings = bo.get("/api/settings").json()
                ada.put("/api/settings", json={"theme": "ink"})
                bo_theme = bo.get("/api/settings").json()["theme"]
                stolen = bo.delete(f"/api/meals/{ada_meal.json()['id']}")
                hidden = bo.get(f"/api/meals/{photo.json()['id']}/image")
                seen = ada.get(f"/api/meals/{photo.json()['id']}/image")
                wrong = anon.post("/api/login", json={"username": "Ada", "password": "nope"})
                logged = anon.post("/api/login", json={"username": "ada", "password": "secret1"})
                bye = anon.post("/api/logout")
                after = anon.get("/api/days/2026-07-04")
                bo_still = bo.get("/api/days/2026-07-04")
                with db.connect() as conn:
                    ada_id = conn.execute(
                        "SELECT id FROM users WHERE username = ?",
                        ("Ada",),
                    ).fetchone()["id"]
                scope = db.set_scope(ada_id)
                try:
                    text = _advice_context("2026-07-04", "1:00 PM", 0)
                finally:
                    db.reset_scope(scope)

            self.assertTrue(opening["authentication"])
            self.assertFalse(opening["has_users"])
            self.assertIn("fox", opening["avatars"])
            self.assertEqual(locked.status_code, 401)
            self.assertEqual(health.json(), {"ok": True})
            self.assertEqual(short.status_code, 400)
            self.assertEqual(bad_face.status_code, 400)
            self.assertEqual(created.status_code, 200)
            self.assertIn("httponly", created.headers["set-cookie"].lower())
            self.assertEqual(created.json()["user"], {"username": "Ada", "avatar": "fox"})
            self.assertNotIn("password_hash", created.text)
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(other.status_code, 200)
            self.assertEqual(ada_settings["daily_goal"], 1800)
            self.assertEqual(ada_settings["protein_goal"], 120)
            self.assertEqual(ada_settings["user"]["avatar"], "fox")
            self.assertEqual(bo_settings["daily_goal"], 2200)
            self.assertEqual(bo_settings["protein_goal"], 160)
            self.assertEqual(bo_theme, "lime")
            self.assertEqual(ada_day["totals"]["calories"], 400)
            self.assertEqual(sorted(meal["title"] for meal in ada_day["meals"]), ["Ada plate", "Ada rice"])
            self.assertEqual(bo_day["totals"]["calories"], 0)
            self.assertEqual(bo_day["meals"], [])
            self.assertEqual(stolen.status_code, 404)
            self.assertEqual(hidden.status_code, 404)
            self.assertEqual(seen.status_code, 200)
            self.assertEqual(wrong.status_code, 401)
            self.assertEqual(logged.status_code, 200)
            self.assertEqual(bye.status_code, 200)
            self.assertEqual(after.status_code, 401)
            self.assertEqual(bo_still.status_code, 200)
            self.assertIn("Ada rice", text)
            self.assertIn("Daily calorie goal: 1800", text)
            self.assertIn("1400 kcal still available", text)
            self.assertNotIn("Shared", text)
        finally:
            os.environ["AUTHENTICATION"] = "false"
            db.set_scope(None)
            if legacy_id is not None:
                db.delete_meal(legacy_id)
            for meal_id in ada_ids:
                db.delete_meal(meal_id)
            with db.connect() as conn:
                conn.execute("DELETE FROM sessions")
                conn.execute("DELETE FROM users")
                conn.execute("DELETE FROM settings WHERE key GLOB '[0-9]*:*'")
