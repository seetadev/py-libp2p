"""LiteLLM access layer.

The rest of the app should only ever call `generate_response(...)` from this
module. Swapping providers/models is then a config change.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised whenever the underlying LLM call fails for any reason."""


def _completion_call(kwargs: dict):
    """
    Run synchronous LiteLLM completion.
    
    We intentionally avoid litellm.acompletion because it can conflict with
    asyncio/trio event loops in some environments.
    """
    import litellm

    return litellm.completion(**kwargs)


async def generate_response(
    prompt: str,
    *,
    system: Optional[str] = None,
    json_mode: bool = False,
    settings: Optional[Settings] = None,
) -> str:
    """Call the configured LLM via LiteLLM and return the text response."""

    settings = settings or get_settings()

    try:
        import litellm
    except ImportError as exc:
        raise LLMError(
            "litellm is not installed. Run `pip install litellm`."
        ) from exc

    messages = []

    if system:
        messages.append(
            {
                "role": "system",
                "content": system,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    kwargs = {
        "model": settings.llm_model,
        "messages": messages,
    }

    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key

    if settings.llm_api_base:
        kwargs["api_base"] = settings.llm_api_base

    if json_mode:
        kwargs["response_format"] = {
            "type": "json_object"
        }

    try:
        # Use normal synchronous LiteLLM call
        # Avoid asyncio/trio conflicts
        response = litellm.completion(**kwargs)

    except Exception as exc:
        logger.error(
            "LLM request failed: %s",
            exc
        )
        raise LLMError(
            f"LLM request failed: {exc}"
        ) from exc

    try:
        content = response["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(
            f"Unexpected LLM response shape: {exc}"
        ) from exc

    if not content:
        raise LLMError(
            "LLM returned an empty response"
        )

    return content


async def generate_json(
    prompt: str,
    *,
    system: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> dict:
    """Convenience wrapper: ask for JSON and parse it."""

    text = await generate_response(
        prompt,
        system=system,
        json_mode=True,
        settings=settings,
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError as exc:
        raise LLMError(
            f"LLM did not return valid JSON: {exc}\nRaw: {text[:500]}"
        ) from exc