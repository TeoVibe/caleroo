"""Turn a food photo into a calorie estimate.

An empty BASE_URL talks to OpenRouter. Any other BASE_URL is an
OpenAI-compatible /v1 server. Both use the same chat-completions call.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-flash"

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


def _http_scheme(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


def _is_openrouter(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme.lower() == "https" and (parts.hostname or "").lower() == "openrouter.ai"


def _chat_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


@dataclass(frozen=True)
class Provider:
    """Where chat completions go. Loaded once at startup."""

    base_url: str
    chat_url: str
    api_key: str
    app_url: str
    default_model: str
    openrouter: bool
    name: str
    problem: str

    def blocking_problem(self, model: str) -> str:
        if self.problem:
            return self.problem
        if not model.strip():
            if self.openrouter:
                return "Choose a model that accepts images."
            return "Set MODEL to a vision model on that server."
        return ""

    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.openrouter:
            headers["HTTP-Referer"] = self.app_url
            headers["X-Title"] = "Caleroo"
        return headers


def load_provider(env: Mapping[str, str] | None = None) -> Provider:
    source = os.environ if env is None else env
    raw = source.get("BASE_URL", "").strip()
    key = source.get("API_KEY", "").strip()
    model = source.get("MODEL", "").strip()
    app_url = source.get("APP_URL", "").strip() or "http://localhost:6969"

    problem = ""
    if not raw:
        base = OPENROUTER_BASE
        openrouter = True
    elif not _http_scheme(raw):
        base = raw
        openrouter = False
        problem = "BASE_URL must start with http:// or https://."
    else:
        base = raw.rstrip("/")
        openrouter = _is_openrouter(base)

    if openrouter and not model:
        model = DEFAULT_MODEL
    if not problem and openrouter and not key:
        problem = "Set API_KEY before using the model."

    return Provider(
        base_url=base,
        chat_url=_chat_url(base) if _http_scheme(base) else "",
        api_key=key,
        app_url=app_url,
        default_model=model,
        openrouter=openrouter,
        name="OpenRouter" if openrouter else "The model server",
        problem=problem,
    )


_provider: Provider | None = None
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


def configure(env: Mapping[str, str] | None = None) -> Provider:
    global _provider
    _provider = load_provider(env)
    return _provider


def get_provider() -> Provider:
    if _provider is None:
        return configure()
    return _provider


def unavailable_reason(model: str) -> str:
    return get_provider().blocking_problem(model)


async def open_client() -> httpx.AsyncClient:
    global _client
    if _client is not None and not _client.is_closed:
        return _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(timeout=90, follow_redirects=False)
        return _client


async def close_client() -> None:
    global _client
    client = _client
    _client = None
    if client is not None and not client.is_closed:
        await client.aclose()


def bind_client(client: httpx.AsyncClient | None) -> None:
    """Point completions at a stand-in client. Tests use this."""
    global _client
    _client = client


def _provider_message(provider: Provider, status: int, body: Any) -> str:
    message = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        elif isinstance(error, str):
            message = error
    message = " ".join(message.split())[:300]
    if status in {401, 403}:
        if provider.openrouter:
            return "OpenRouter rejected the API key."
        return f"{provider.name} rejected the request."
    if status == 402 and provider.openrouter:
        return "OpenRouter says this account has no credit left."
    if status == 429:
        return f"{provider.name} is rate limiting requests. Wait a moment and try again."
    if status == 404:
        return message or "That model was not found."
    return message or f"{provider.name} returned status {status}."


async def _post(
    client: httpx.AsyncClient,
    provider: Provider,
    payload: dict,
    timeout: float,
) -> dict:
    try:
        response = await client.post(
            provider.chat_url,
            headers=provider.headers(),
            json=payload,
            timeout=timeout,
        )
    except httpx.TimeoutException as exc:
        raise EstimatorError("The model took too long. Try again.") from exc
    except httpx.HTTPError as exc:
        if provider.openrouter:
            raise EstimatorError("Could not reach OpenRouter.") from exc
        raise EstimatorError("Could not reach the model server. Check BASE_URL.") from exc
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if response.status_code >= 400 or not isinstance(body, dict) or "choices" not in body:
        raise EstimatorError(_provider_message(provider, response.status_code, body), response.status_code)
    return body


async def _complete(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    provider = get_provider()
    reason = provider.blocking_problem(model)
    if reason:
        raise EstimatorError(reason)
    if not provider.chat_url:
        raise EstimatorError("Set BASE_URL to an OpenAI-compatible endpoint, like http://host:8000/v1.")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    client = await open_client()
    try:
        body = await _post(
            client,
            provider,
            {**payload, "response_format": {"type": "json_object"}},
            timeout,
        )
    except EstimatorError as exc:
        if exc.status != 400:
            raise
        body = await _post(client, provider, payload, timeout)

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise EstimatorError(f"{provider.name} returned an empty reply. Try again.") from exc
    text = _message_text(content).strip()
    if not text:
        raise EstimatorError(f"{provider.name} returned an empty reply. Try again.")
    return text


async def estimate_calories(image: bytes, media_type: str, *, model: str) -> dict[str, Any]:
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
    text = await _complete(messages, model=model, temperature=0.2, max_tokens=1500, timeout=90)
    estimate = normalize_estimate(extract_json(text))
    estimate["model"] = model
    return estimate


ADVICE_PROMPT = """Suggest what to eat for the rest of today, using this calorie log.

Reply with one JSON object and no other text:
{
  "summary": "one or two sentences on the rest of the day",
  "ideas": [
    {
      "title": "short meal or snack name",
      "detail": "one sentence on why it fits",
      "calories": 0
    }
  ]
}

Rules:
- Give 2 or 3 concrete ideas that fit the calories still available.
- Use ordinary foods, and match the time of day.
- The only target is the calorie goal. Do not invent protein or macro targets.
- If little room is left, suggest a small snack, or say they can stop.
- If they are already over the goal, do not push more food. Say so, and offer one light option only if they might still be hungry.
- If nothing is logged yet, suggest a simple plan for the meals still ahead today.
- calories is an integer estimate for that idea.
- This is practical meal planning, not medical advice. Do not diagnose or recommend extreme restriction.
"""


def normalize_advice(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _text(payload.get("summary"), 400)
    raw_ideas = payload.get("ideas") or []
    if not isinstance(raw_ideas, list):
        raw_ideas = []
    ideas = []
    for raw in raw_ideas[:8]:
        if len(ideas) == 3:
            break
        if not isinstance(raw, dict):
            continue
        title = _text(raw.get("title"), 80)
        if not title:
            continue
        ideas.append(
            {
                "title": title,
                "detail": _text(raw.get("detail"), 240),
                "calories": int(round(_number(raw.get("calories")))),
            }
        )
    if not summary and not ideas:
        raise EstimatorError("The model reply had no advice. Try again.")
    return {"summary": summary, "ideas": ideas}


async def advise_rest_of_day(context: str, *, model: str) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": "You suggest ordinary meals that fit a calorie log. You only reply with JSON.",
        },
        {"role": "user", "content": f"{ADVICE_PROMPT}\n\nLog:\n{context}"},
    ]
    text = await _complete(messages, model=model, temperature=0.5, max_tokens=800, timeout=60)
    return normalize_advice(extract_json(text))
