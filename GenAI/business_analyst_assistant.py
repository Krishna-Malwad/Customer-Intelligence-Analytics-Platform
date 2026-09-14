"""
business_analyst_assistant.py
==============================
Answers open-ended business questions ("Why did sales decrease?",
"Which customers generate highest revenue?") by first computing the
relevant real numbers from the cleaned data with pandas, THEN asking
Claude to explain/interpret those numbers.

Design principle — compute first, explain second:
----------------------------------------------------
We never let the LLM invent numbers. Every fact in its answer is
grounded in a pandas computation done in this script. Claude's job is
interpretation and narrative, not arithmetic — this avoids the most
common GenAI-analytics failure mode (confidently wrong numbers).

Run:
    python business_analyst_assistant.py "Why might revenue have dropped in a given month?"
"""

import sys
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "Python"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "EDA"))
import etl_pipeline  # noqa: E402
import eda_analysis  # noqa: E402
from genai_client import ask_claude  # noqa: E402

SYSTEM_PROMPT = """You are a senior e-commerce business analyst for a Brazilian
marketplace (Olist). You will be given real, pre-computed metrics — never invent
numbers not present in the input. Explain what the data shows, propose plausible
business reasons for the pattern (grounded in the metrics given), and end with 1-2
concrete recommendations. Keep it to 4-6 sentences plus recommendations."""


def gather_context(data_dir: str) -> dict:
    raw = etl_pipeline.extract(Path(data_dir))
    clean = etl_pipeline.transform(raw)
    order_value = eda_analysis.build_order_value_table(clean)

    return {
        "customer_intelligence": eda_analysis.customer_intelligence(clean, order_value),
        "sales_analysis": eda_analysis.sales_analysis(order_value, clean),
        "order_analysis": eda_analysis.order_analysis(clean),
        "payment_analysis": eda_analysis.payment_analysis(clean),
        "review_analysis": eda_analysis.review_analysis(clean),
    }


def format_context_for_prompt(context: dict) -> str:
    lines = []
    for section, metrics in context.items():
        lines.append(f"## {section}")
        for k, v in metrics.items():
            # Keep prompts compact: summarize long series instead of dumping them
            if hasattr(v, "to_dict") and len(v) > 8:
                v = dict(list(v.to_dict().items())[:8])
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def ask(question: str, data_dir: str) -> str:
    context = gather_context(data_dir)
    context_text = format_context_for_prompt(context)
    prompt = f"Business question: {question}\n\nAvailable metrics:\n{context_text}"
    return ask_claude(SYSTEM_PROMPT, prompt, max_tokens=800)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    answer = ask(args.question, args.data_dir)
    print(answer)
