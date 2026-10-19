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
from app.main import app  # noqa: E402
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
        self.assertNotIn("inference", body)
        self.assertIn("Set API_KEY", page)
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
        self.assertIn("by hand", photo.json()["detail"])
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
