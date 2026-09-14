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

import sys
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent / "GenAI"))

logger = logging.getLogger(__name__)


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
