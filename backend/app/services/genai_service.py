"""
services/genai_service.py
===========================
Wraps the existing GenAI/ scripts (unchanged) for use from FastAPI
routes. Reuses genai_client.py and nl_to_sql_assistant.py's safety
logic directly â€” no duplicated Gemini-calling code.

Every function here can genuinely fail (no Gemini key configured, the
Gemini API being down, a malformed response) â€” each failure mode is
caught and returned as a structured, non-crashing error rather than
propagating a raw exception to the client.
"""

import re
import sys
import socket
import ipaddress
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent / "GenAI"))

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Dashboard-URL fetch limits (Chart Insight Generator, Mode A)
# ------------------------------------------------------------------
_FETCH_TIMEOUT_SECONDS = 8
_MAX_FETCH_BYTES = 2 * 1024 * 1024  # 2 MB
_MAX_CONTEXT_CHARS = 8000


class GenAIError(Exception):
    """Raised for any GenAI-layer failure â€” missing key, API error, bad SQL, etc."""
    pass


def ask_business_question(question: str, context_text: str) -> dict:
    try:
        from genai_client import ask_claude
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    system_prompt = (
        "You are a senior e-commerce business analyst. You will be given real, "
        "pre-computed metrics â€” never invent numbers not present in the input. "
        "Explain what the data shows and give 1-2 concrete recommendations. All monetary values are in Brazilian Real (BRL). Always use the currency symbol R$ for monetary values, never $ or USD\."
    )
    try:
        answer = ask_claude(system_prompt, f"Question: {question}\n\nMetrics:\n{context_text}", max_tokens=800)
        return {"question": question, "answer": answer}
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        logger.exception("GenAI business question failed")
        raise GenAIError(f"GenAI request failed: {e}")


def natural_language_to_sql(question: str, cursor) -> dict:
    try:
        from nl_to_sql_assistant import generate_sql, is_safe_select, execute_sql, explain_result
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    try:
        gen = generate_sql(question)
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        raise GenAIError(f"SQL generation failed: {e}")

    sql = gen.get("sql", "")
    if not is_safe_select(sql):
        raise GenAIError("Generated SQL failed the read-only safety check and was not executed.")

    try:
        df = execute_sql(sql, cursor=cursor)
    except Exception as e:
        raise GenAIError(f"SQL execution failed: {e}")

    if df.empty:
        explanation = "The query ran successfully but returned no rows."
    else:
        try:
            explanation = explain_result(question, df)
        except Exception as e:
            explanation = f"(Explanation unavailable: {e})"

    return {
        "question": question,
        "generated_sql": sql,
        "reasoning": gen.get("reasoning", ""),
        "row_count": len(df),
        "results": df.head(50).to_dict(orient="records"),
        "explanation": explanation,
    }


# ============================================================
# AUTOMATED INSIGHTS
# ============================================================

def generate_automated_insights(context_text: str) -> dict:
    """
    Ask Gemini to surface trends, patterns, and anomalies from real,
    pre-computed analytics. Reuses the same shared Gemini client as
    ask_business_question - no new AI client is created.
    """
    try:
        from genai_client import ask_claude
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    system_prompt = (
        "You are a senior e-commerce business analyst producing an automated "
        "insights briefing. You will be given real, pre-computed metrics - "
        "never invent numbers not present in the input. Identify the most "
        "important trends, patterns, and anomalies across revenue, customers, "
        "delivery, and satisfaction. Structure the answer as short labeled "
        "sections (for example: Revenue, Customers, Delivery, Satisfaction, "
        "Notable Anomalies), each with 1-3 concise sentences. Only describe "
        "something as a trend or anomaly if the provided data actually "
        "supports it; if a category has nothing notable, say so briefly "
        "rather than inventing a signal. All monetary values are in Brazilian "
        "Real (BRL). Always use the currency symbol R$, never $ or USD."
    )

    try:
        answer = ask_claude(
            system_prompt,
            f"Metrics:\n{context_text}",
            max_tokens=900,
        )
        return {"insights": answer}
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        logger.exception("GenAI automated insights generation failed")
        raise GenAIError(f"GenAI request failed: {e}")


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_business_report(context_text: str) -> dict:
    """
    Ask Gemini for a structured, multi-section business report built only
    from real analytics context. Uses ask_claude_json (already provided by
    the shared Gemini client) so the report renders as clean sections in
    the UI instead of one wall of text.
    """
    try:
        from genai_client import ask_claude_json
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    system_prompt = (
        "You are a senior e-commerce business analyst producing a structured "
        "business report. You will be given real, pre-computed metrics - "
        "never invent numbers or claims not present in the input. Respond "
        "with a JSON object containing exactly these string keys: "
        "\"executive_summary\", \"revenue_and_customer_performance\", "
        "\"product_performance\", \"delivery_and_operations\", "
        "\"customer_satisfaction\", \"key_findings\", "
        "\"recommended_areas_of_attention\". Each value should be 2-5 "
        "sentences of clear, readable prose grounded strictly in the given "
        "metrics (key_findings and recommended_areas_of_attention may each "
        "be written as 2-4 short numbered sentences). All monetary values "
        "are in Brazilian Real (BRL). Always use the currency symbol R$, "
        "never $ or USD."
    )

    try:
        report = ask_claude_json(
            system_prompt,
            f"Metrics:\n{context_text}",
            max_tokens=1800,
        )
        return {"report": report}
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        logger.exception("GenAI report generation failed")
        raise GenAIError(f"GenAI request failed: {e}")


# ============================================================
# DASHBOARD / CHART INSIGHT GENERATOR
# ============================================================

def _is_safe_public_host(hostname: str) -> bool:
    """
    Resolve the hostname and reject anything that maps to a private,
    loopback, link-local, reserved, or multicast address - a basic SSRF
    guard for the public-dashboard-URL fetch below.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    if not infos:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False

    return True


def _fetch_public_url_text(url: str):
    """
    Best-effort fetch of a PUBLIC dashboard URL's page text.

    Returns (extracted_text, note). Never raises for network or validation
    failures - returns an explanatory note instead, so the caller can pass
    that context straight to Gemini (or surface it to the user) instead of
    the request crashing.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return "", (
            "The provided URL could not be fetched: only http:// and "
            "https:// URLs are supported."
        )

    if not parsed.hostname:
        return "", "The provided URL could not be fetched: no hostname found."

    if not _is_safe_public_host(parsed.hostname):
        return "", (
            "The provided URL points to a private, local, or reserved "
            "network address and was not fetched for security reasons. "
            "Only publicly accessible dashboard URLs are supported."
        )

    try:
        resp = requests.get(
            url,
            timeout=_FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "CustomerIntelligenceBot/1.0"},
            stream=True,
        )
        resp.raise_for_status()

        raw = b""
        for chunk in resp.iter_content(8192):
            if not chunk:
                continue
            raw += chunk
            if len(raw) >= _MAX_FETCH_BYTES:
                break

        html = raw.decode(resp.encoding or "utf-8", errors="ignore")

    except requests.exceptions.RequestException as e:
        return "", (
            f"The provided URL could not be fetched ({e}). If this "
            "dashboard requires authentication or login, it cannot be "
            "analyzed this way - please upload a screenshot instead."
        )

    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return "", (
            "The page was fetched successfully, but no readable text "
            "content was found. This dashboard likely renders its charts "
            "using JavaScript, which cannot be read from the raw page - "
            "please upload a screenshot instead for accurate analysis."
        )

    truncated = text[:_MAX_CONTEXT_CHARS]
    note = (
        "The following is raw extracted text from the public page (not a "
        "rendered screenshot). If the dashboard is a JavaScript-rendered "
        "app, this text may be incomplete or may not reflect the actual "
        "charts - treat it as a best-effort summary only."
    )
    return truncated, note


def analyze_dashboard_url(url: str) -> dict:
    """
    Chart Insight Generator, Mode A: analyze a PUBLIC dashboard URL.
    Fetches the page text with basic SSRF protection, then reuses the
    shared Gemini client (ask_claude) to interpret it.
    """
    try:
        from genai_client import ask_claude
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    page_text, fetch_note = _fetch_public_url_text(url)

    system_prompt = (
        "You are a senior e-commerce business analyst analyzing a public "
        "dashboard page on behalf of a user. You are given the extracted "
        "textual content of the page, which may be incomplete if the "
        "dashboard renders its charts using JavaScript. Identify trends, "
        "patterns, comparisons, and anomalies ONLY where the provided "
        "content actually supports them. If the content does not contain "
        "enough information to analyze the dashboard's charts, say so "
        "plainly and recommend the user upload a screenshot instead. Do "
        "not invent values you cannot see in the provided content."
    )
    user_prompt = (
        f"Dashboard URL: {url}\n\n{fetch_note}\n\n"
        f"Extracted page content:\n{page_text or '(no readable text content)'}"
    )

    try:
        answer = ask_claude(system_prompt, user_prompt, max_tokens=900)
        return {"url": url, "fetch_note": fetch_note, "analysis": answer}
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        logger.exception("GenAI dashboard URL analysis failed")
        raise GenAIError(f"GenAI request failed: {e}")


def analyze_dashboard_image(image_base64: str, media_type: str) -> dict:
    """
    Chart Insight Generator, Mode B: analyze an uploaded dashboard
    screenshot. Reuses the shared Gemini client's existing vision function
    (ask_claude_vision) - no new AI client is created.
    """
    try:
        from genai_client import ask_claude_vision
    except ImportError as e:
        raise GenAIError(f"GenAI module not available: {e}")

    system_prompt = (
        "You are a senior e-commerce business analyst analyzing a "
        "screenshot of a business dashboard or chart. Identify major "
        "trends, changes, anomalies, high/low performers, relationships "
        "between series, and business implications that are actually "
        "visible in the image. If a value, label, or trend is unclear or "
        "unreadable, say so explicitly instead of guessing. Do not invent "
        "numbers that are not visibly shown in the screenshot."
    )
    user_prompt = (
        "Analyze this dashboard/chart screenshot and explain what it "
        "shows, including any trends, anomalies, or business implications."
    )

    try:
        answer = ask_claude_vision(
            system_prompt,
            user_prompt,
            image_base64,
            media_type=media_type,
            max_tokens=900,
        )
        return {"analysis": answer}
    except EnvironmentError as e:
        raise GenAIError(f"Gemini API key not configured: {e}")
    except Exception as e:
        logger.exception("GenAI dashboard screenshot analysis failed")
        raise GenAIError(f"GenAI request failed: {e}")