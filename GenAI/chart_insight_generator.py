"""
chart_insight_generator.py
============================
User uploads a chart/dashboard image, asks a question ("explain this
chart"), and Claude's vision capability analyzes trends, patterns, and
possible business causes directly from the image.

Unlike the other GenAI scripts, this one legitimately needs the LLM to
"see" data it wasn't given numerically — that's the whole point of the
feature — so there's no rule-based grounding step here. To keep answers
honest, the system prompt explicitly tells Claude to flag uncertainty
about exact values it can't read precisely off the image.

Run:
    python chart_insight_generator.py path/to/chart.png "What's driving the Q3 dip?"
"""

import sys
import base64
import argparse
import mimetypes
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from genai_client import ask_claude_vision  # noqa: E402

SYSTEM_PROMPT = """You are a business intelligence analyst reviewing a chart or
dashboard screenshot. Describe: (1) what type of chart it is and what it measures,
(2) the main trend or pattern visible, (3) any notable outliers or inflection points,
(4) 1-2 plausible business explanations, (5) one recommendation. If you cannot read an
exact number precisely from the image, say so rather than guessing a specific figure."""

SUPPORTED_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def encode_image(image_path: str) -> tuple:
    path = Path(image_path)
    ext = path.suffix.lower()
    media_type = SUPPORTED_TYPES.get(ext) or mimetypes.guess_type(image_path)[0]
    if media_type not in SUPPORTED_TYPES.values():
        raise ValueError(f"Unsupported image type: {ext}. Supported: {list(SUPPORTED_TYPES.keys())}")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, media_type


def explain_chart(image_path: str, question: str = "Explain this chart.") -> str:
    image_b64, media_type = encode_image(image_path)
    return ask_claude_vision(SYSTEM_PROMPT, question, image_b64, media_type=media_type)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("question", nargs="?", default="Explain this chart.")
    args = parser.parse_args()
    print(explain_chart(args.image_path, args.question))
