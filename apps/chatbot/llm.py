import logging
import math
import re
import time
from typing import Any

import httpx
from django.conf import settings

from .models import ModelInvocation

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """Exception for LLM/Embedding provider issues."""


def _endpoint(path: str) -> str:
    base = getattr(settings, "LLM_BASE_URL", "")
    if not base:
        raise LLMUnavailable("LLM_BASE_URL not configured")
    if base.endswith("/v1"):
        return f"{base}/{path.lstrip('/')}"
    return f"{base.rstrip('/')}/v1/{path.lstrip('/')}"


def _headers() -> dict[str, str]:
    api_key = getattr(settings, "LLM_API_KEY", "")
    if not api_key:
        raise LLMUnavailable("LLM_API_KEY not configured")
    return {"Authorization": f"Bearer {api_key}"}


def _record_invocation(
    purpose: str,
    started: float,
    error_code: str | None = None,
) -> None:
    try:
        model_name = (
            getattr(settings, "EMBEDDING_MODEL", "mock-embedding")
            if purpose == ModelInvocation.Purpose.EMBEDDING
            else getattr(settings, "LLM_MODEL", "mock-llm")
        )

        ModelInvocation.objects.create(
            purpose=purpose,
            model=model_name or "mock-model",
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            succeeded=error_code is None,
            error_code=error_code,
        )
    except Exception:
        pass


def _demo_completion(messages: list[dict[str, str]]) -> str:
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break
    matches = re.findall(
        r"id:\s*(\d+)\s*\|\s*name:\s*([^|\n]+)\s*\|\s*price:\s*([^|\n]+)",
        user_query,
        flags=re.IGNORECASE,
    )
    if matches:
        options = "; ".join(
            f"{name.strip()} (#{product_id}, {price.strip()})"
            for product_id, name, price in matches[:4]
        )
        return (
            f"Demo mode (AI provider not configured): catalog matches include {options}. "
            "Tell me your budget and intended use, and I can narrow these down. "
            "For a PC build, verify processor, motherboard, memory, case, and power compatibility before ordering."
        )
    return (
        "Demo mode (AI provider not configured): I couldn’t find a close catalog match. Tell me the component or setup you need, "
        "your budget, and any compatibility requirements, and I’ll help you search the available options."
    )


def embed_text(text: str) -> list[float]:
    started = time.monotonic()
    emb_model = getattr(settings, "EMBEDDING_MODEL", "")
    api_key = getattr(settings, "LLM_API_KEY", "")

    if not emb_model or not api_key:
        _record_invocation("embedding", started, "provider_not_configured")
        raise LLMUnavailable("Embedding provider is not configured.")

    try:
        response = httpx.post(
            _endpoint("embeddings"),
            headers=_headers(),
            json={"model": emb_model, "input": text},
            timeout=getattr(settings, "LLM_TIMEOUT_SECONDS", 30),
        )
        if response.is_error:
            _record_invocation("embedding", started, f"provider_http_error_{response.status_code}")
            raise LLMUnavailable(f"Embedding provider returned HTTP {response.status_code}.")

        data = response.json()
        vector = data.get("data", [{}])[0].get("embedding")
        dimension = int(getattr(settings, "EMBEDDING_DIMENSION", 1536) or 1536)
        if (
            not isinstance(vector, list)
            or len(vector) != dimension
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in vector
            )
        ):
            _record_invocation("embedding", started, "provider_invalid_vector")
            raise LLMUnavailable("Embedding provider returned a vector with an unexpected dimension.")

        _record_invocation("embedding", started)
        return vector

    except LLMUnavailable:
        raise
    except Exception as exc:
        _record_invocation("embedding", started, "provider_error")
        raise LLMUnavailable("Embedding provider request failed.") from exc


def chat_completion(messages: list[dict[str, str]], **kwargs: Any) -> str:
    started = time.monotonic()
    api_key = getattr(settings, "LLM_API_KEY", "")
    llm_model = getattr(settings, "LLM_MODEL", "")

    if not api_key or not llm_model:
        response_text = _demo_completion(messages)
        _record_invocation("chat", started, "mock_mode")
        return response_text

    try:
        payload = {
            "model": llm_model,
            "messages": messages,
            **kwargs,
        }
        response = httpx.post(
            _endpoint("chat/completions"),
            headers=_headers(),
            json=payload,
            timeout=getattr(settings, "LLM_TIMEOUT_SECONDS", 30),
        )
        if response.is_error:
            _record_invocation("chat", started, f"provider_http_error_{response.status_code}")
            raise LLMUnavailable(f"Chat provider returned HTTP {response.status_code}.")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            _record_invocation("chat", started, "provider_invalid_response")
            raise LLMUnavailable("Chat provider returned an empty or invalid response.")
        _record_invocation("chat", started)
        return content
    except LLMUnavailable:
        raise
    except Exception as exc:
        _record_invocation("chat", started, "provider_error")
        raise LLMUnavailable("Chat provider request failed.") from exc


generate_chat_response = chat_completion
