"""Turn a food photo into a calorie estimate.

INFERENCE=openrouter talks to OpenRouter. INFERENCE=local talks to any
OpenAI-compatible /v1 server at LOCAL_BASE_URL.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

import httpx

PROMPT = """Estimate the calories in this photograph of food.

Reply with one JSON object and no other text:
{
  "title": "short name for the whole plate",
  "items": [
    {
      "name": "food name",
      "portion": "amount you assumed",
      "calories": 0,
      "protein_g": 0,
      "carbs_g": 0,
      "fat_g": 0
    }
  ],
  "notes": "one short sentence on the assumptions",
  "confidence": "low"
}

Rules:
- List every distinct food you can see, including drinks, sauces, oil, and dressings.
- calories is an integer. Macros are grams.
- If the portion is unclear, use a typical serving and say so in notes.
- If no food is visible, use an empty items array, title "No food detected", and confidence "low".
- Do not invent foods that are not visible.
- confidence is "low", "medium", or "high".
"""


class EstimatorError(Exception):
    """The photo could not be estimated."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def sniff_image(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return None


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise EstimatorError("The model reply was not valid JSON. Try the photo again.") from None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise EstimatorError("The model reply was not valid JSON. Try the photo again.") from exc
    if not isinstance(parsed, dict):
        raise EstimatorError("The model reply was not a JSON object. Try the photo again.")
    return parsed


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0 or number > 20000:
        return 0.0
    return number


def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return text[:limit]


def normalize_estimate(payload: dict[str, Any]) -> dict[str, Any]:
    raw_items = payload.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []
    items = []
    for raw in raw_items[:24]:
        if not isinstance(raw, dict):
            continue
        name = _text(raw.get("name"), 80)
        if not name:
            continue
        items.append(
            {
                "name": name,
                "portion": _text(raw.get("portion"), 48),
                "calories": int(round(_number(raw.get("calories")))),
                "protein_g": round(_number(raw.get("protein_g")), 1),
                "carbs_g": round(_number(raw.get("carbs_g")), 1),
                "fat_g": round(_number(raw.get("fat_g")), 1),
            }
        )
    title = _text(payload.get("title"), 80)
    if not title:
        title = ", ".join(item["name"] for item in items[:3]) or "Meal"
    confidence = payload.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        confidence = "low" if not items else "medium"
    totals = sum_items(items)
    return {
        "title": title,
        "items": items,
        "notes": _text(payload.get("notes"), 280),
        "confidence": confidence,
        **totals,
    }


def sum_items(items: list[dict[str, Any]]) -> dict[str, float | int]:
    return {
        "calories": int(round(sum(_number(item.get("calories")) for item in items))),
        "protein_g": round(sum(_number(item.get("protein_g")) for item in items), 1),
        "carbs_g": round(sum(_number(item.get("carbs_g")) for item in items), 1),
        "fat_g": round(sum(_number(item.get("fat_g")) for item in items), 1),
    }


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content") or ""
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return "" if content is None else str(content)


def inference_mode() -> str:
    return os.environ.get("INFERENCE", "openrouter").strip().lower() or "openrouter"


def provider_name() -> str:
    return "OpenRouter" if inference_mode() == "openrouter" else "The model server"


def chat_completions_url() -> str:
    mode = inference_mode()
    if mode == "local":
        base = os.environ.get("LOCAL_BASE_URL", "").strip()
        if not base:
            raise EstimatorError("Set LOCAL_BASE_URL to an OpenAI-compatible endpoint, like http://host:8000/v1.")
        if not base.startswith(("http://", "https://")):
            raise EstimatorError("LOCAL_BASE_URL must start with http:// or https://.")
    elif mode == "openrouter":
        base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    else:
        raise EstimatorError("INFERENCE must be openrouter or local.")
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def request_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if inference_mode() == "local":
        key = os.environ.get("LOCAL_API_KEY", "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise EstimatorError("Set OPENROUTER_API_KEY before estimating a photo.")
    headers["Authorization"] = f"Bearer {key}"
    headers["HTTP-Referer"] = os.environ.get("APP_URL", "http://localhost:6969")
    headers["X-Title"] = "Caleroo"
    return headers


def estimates_ready() -> bool:
    mode = inference_mode()
    if mode == "local":
        return bool(os.environ.get("LOCAL_BASE_URL", "").strip())
    if mode == "openrouter":
        return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    return False


def _provider_message(status: int, body: Any) -> str:
    name = provider_name()
    message = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        elif isinstance(error, str):
            message = error
    message = " ".join(message.split())[:300]
    if status in {401, 403}:
        if inference_mode() == "openrouter":
            return "OpenRouter rejected the API key."
        return f"{name} rejected the request."
    if status == 402 and inference_mode() == "openrouter":
        return "OpenRouter says this account has no credit left."
    if status == 429:
        return f"{name} is rate limiting requests. Wait a moment and try again."
    if status == 404:
        return message or "That model was not found."
    return message or f"{name} returned status {status}."


async def _post(client: httpx.AsyncClient, url: str, headers: dict[str, str], payload: dict) -> dict:
    try:
        response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise EstimatorError("The model took too long. Try again.") from exc
    except httpx.HTTPError as exc:
        if inference_mode() == "local":
            raise EstimatorError("Could not reach the model server. Check LOCAL_BASE_URL.") from exc
        raise EstimatorError("Could not reach OpenRouter.") from exc
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if response.status_code >= 400 or not isinstance(body, dict) or "choices" not in body:
        raise EstimatorError(_provider_message(response.status_code, body), response.status_code)
    return body


async def estimate_calories(image: bytes, media_type: str, *, model: str) -> dict[str, Any]:
    if inference_mode() == "local" and not model:
        raise EstimatorError("Set LOCAL_MODEL to a vision model on that server.")
    if not model:
        raise EstimatorError("Choose a model that accepts images.")

    data_url = f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"
    messages = [
        {"role": "system", "content": "You are a careful nutrition estimator. You only reply with JSON."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    base_payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 1500}
    url = chat_completions_url()
    headers = request_headers()
    name = provider_name()

    async with httpx.AsyncClient(timeout=90) as client:
        try:
            body = await _post(
                client,
                url,
                headers,
                {**base_payload, "response_format": {"type": "json_object"}},
            )
        except EstimatorError as exc:
            if exc.status != 400:
                raise
            body = await _post(client, url, headers, base_payload)

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise EstimatorError(f"{name} returned an empty reply. Try again.") from exc
    estimate = normalize_estimate(extract_json(_message_text(content)))
    estimate["model"] = model
    return estimate
