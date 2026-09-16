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
this is the ONLY file that needs to change.

Requires:
    pip install requests
    GEMINI_API_KEY=...

This module makes NO network calls at import time — it only connects
when a function is actually invoked, so the rest of the project can
import it safely even without a key configured.
"""

import os
import json
import logging

import requests

try:
    from dotenv import load_dotenv

    # Loads the project-level .env file when running locally.
    load_dotenv()

except ImportError:
    # Falls back to normal environment variables when
    # python-dotenv is not installed.
    pass


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-3.6-flash"

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
)


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """
    Get the Gemini API key from the environment.

    The key should be stored in the project .env file locally
    or configured as an environment variable in production.
    """

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add GEMINI_API_KEY to the project .env file "
            "or configure it as an environment variable."
        )

    return api_key


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_text(response_json: dict) -> str:
    """
    Pull plain generated text out of a Gemini generateContent response.
    """

    try:
        candidates = response_json["candidates"]

        if not candidates:
            raise RuntimeError(
                "Gemini returned no candidates."
            )

        parts = candidates[0]["content"]["parts"]

        return "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict)
        )

    except (KeyError, IndexError, TypeError) as e:

        # Log the response for debugging, but NEVER log the API key.
        logger.error(
            "Unexpected Gemini response shape: %s",
            response_json,
        )

        raise RuntimeError(
            f"Could not extract text from Gemini response: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Text generation
# ---------------------------------------------------------------------------

def ask_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1500,
) -> str:
    """
    Single-turn text completion using Gemini.

    The function name remains 'ask_claude' for backward compatibility
    with the existing GenAI scripts.

    Existing imports such as:

        from genai_client import ask_claude

    continue to work without modification.
    """

    api_key = _get_api_key()

    url = f"{GEMINI_BASE_URL}/{model}:generateContent"

    # IMPORTANT:
    # Send the API key through the header instead of putting it
    # directly into the URL.
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        },

        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_prompt
                    }
                ]
            }
        ],

        "generationConfig": {
            "maxOutputTokens": max(max_tokens, 1024) + 512,

            # Preserve the existing project's behavior.
            "thinkingConfig": {
                "thinkingBudget": 0
            },
        },
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
        )

        response.raise_for_status()

    except requests.RequestException as e:

        logger.error(
            "Gemini text generation request failed: %s",
            e,
        )

        raise RuntimeError(
            f"Gemini API request failed: {e}"
        ) from e

    return _extract_text(response.json())


# ---------------------------------------------------------------------------
# JSON generation
# ---------------------------------------------------------------------------

def ask_claude_json(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1500,
) -> dict:
    """
    Generate a JSON response using Gemini.

    Used by structured GenAI workflows such as:

    - Natural Language → SQL
    - Automated Insights
    - Report Generation

    The function name remains unchanged for compatibility.
    """

    json_system_prompt = (
        system_prompt
        + "\n\n"
        "CRITICAL OUTPUT REQUIREMENT: "
        "Respond with ONLY a valid JSON object. "
        "Do not use Markdown code fences. "
        "Do not include a preamble. "
        "Do not include any explanation outside the JSON."
    )

    raw = ask_claude(
        json_system_prompt,
        user_prompt,
        model=model,
        max_tokens=max_tokens,
    )

    cleaned = raw.strip()

    # Handle accidental Markdown code fences.
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]

    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:

        return json.loads(cleaned)

    except json.JSONDecodeError as e:

        logger.error(
            "Model did not return valid JSON. Raw output:\n%s",
            raw,
        )

        raise RuntimeError(
            f"Gemini returned invalid JSON: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Vision / screenshot analysis
# ---------------------------------------------------------------------------

def ask_claude_vision(
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
    media_type: str = "image/png",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1200,
) -> str:
    """
    Vision completion using Gemini.

    Used by the Dashboard Analyst / Chart Insight Generator
    screenshot workflow.

    The image is sent directly to Gemini as base64 inline data.
    """

    if not image_base64:
        raise ValueError(
            "image_base64 cannot be empty."
        )

    if not media_type:
        raise ValueError(
            "media_type cannot be empty."
        )

    api_key = _get_api_key()

    url = f"{GEMINI_BASE_URL}/{model}:generateContent"

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        },

        "contents": [
            {
                "role": "user",

                "parts": [
                    {
                        "inline_data": {
                            "mime_type": media_type,
                            "data": image_base64,
                        }
                    },
                    {
                        "text": user_prompt
                    },
                ],
            }
        ],

        "generationConfig": {
            "maxOutputTokens": max(max_tokens, 1024) + 512,

            # Preserve the existing project behavior.
            "thinkingConfig": {
                "thinkingBudget": 0
            },
        },
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
        )

        response.raise_for_status()

    except requests.RequestException as e:

        logger.error(
            "Gemini vision request failed: %s",
            e,
        )

        raise RuntimeError(
            f"Gemini API vision request failed: {e}"
        ) from e

    return _extract_text(response.json())