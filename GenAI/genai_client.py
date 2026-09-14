"""
genai_client.py  (Gemini version)
===================================
Thin wrapper around the Google Gemini API, shared by every GenAI script
in this project (business analyst assistant, NL-to-SQL, insight
generator, report generator, chart insight generator).

This file was originally written against Anthropic's Claude API and has
been swapped to call Google's Gemini API instead. The function names
(ask_claude, ask_claude_json, ask_claude_vision) are kept IDENTICAL on
purpose — every other script in GenAI/ imports these exact names, so
this is the ONLY file that needed to change. Think of these names as
"ask the LLM" rather than literally "ask Claude" at this point.

Requires:
    pip install requests
    export GEMINI_API_KEY=AIza...

This module makes NO network calls at import time — it only connects
when a function is actually invoked, so the rest of the project can
import it safely even without a key configured (e.g. during testing).
"""

import os
import json
import base64
import logging

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a .env file in the current/parent directory, if present
except ImportError:
    pass  # python-dotenv not installed; falls back to normal environment variables

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Export it before running any GenAI script:\n"
            "  export GEMINI_API_KEY=AIza..."
        )
    return api_key


def _extract_text(response_json: dict) -> str:
    """Pull the plain text out of a Gemini generateContent response."""
    try:
        candidates = response_json["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as e:
        logger.error("Unexpected Gemini response shape: %s", response_json)
        raise RuntimeError(f"Could not extract text from Gemini response: {e}")


def ask_claude(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL,
                max_tokens: int = 1500) -> str:
    """Single-turn text completion. Returns the plain text response.

    Name kept as 'ask_claude' for compatibility with the other GenAI scripts
    that import it — internally this now calls Gemini.
    """
    api_key = _get_api_key()
    url = f"{GEMINI_BASE_URL}/{model}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max(max_tokens, 1024) + 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return _extract_text(response.json())


def ask_claude_json(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL,
                     max_tokens: int = 1500) -> dict:
    """
    Same as ask_claude, but instructs the model to return ONLY JSON and
    parses it. Used by nl_to_sql_assistant.py where we need a structured
    {sql, explanation} object back, not free text.
    """
    json_system_prompt = (
        system_prompt
        + "\n\nCRITICAL: Respond with ONLY a valid JSON object. "
          "No markdown code fences, no preamble, no explanation outside the JSON."
    )
    raw = ask_claude(json_system_prompt, user_prompt, model=model, max_tokens=max_tokens)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Model did not return valid JSON. Raw output:\n%s", raw)
        raise


def ask_claude_vision(system_prompt: str, user_prompt: str, image_base64: str,
                       media_type: str = "image/png", model: str = DEFAULT_MODEL,
                       max_tokens: int = 1200) -> str:
    """Vision completion for chart_insight_generator.py — describe/analyze an uploaded image."""
    api_key = _get_api_key()
    url = f"{GEMINI_BASE_URL}/{model}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": image_base64}},
                {"text": user_prompt},
            ],
        }],
        "generationConfig": {
            "maxOutputTokens": max(max_tokens, 1024) + 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return _extract_text(response.json())