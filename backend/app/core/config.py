"""
config.py
=========
Centralized configuration, reading from the same .env file used by the
rest of the project (Python/ and GenAI/ scripts). No secrets are ever
hardcoded here — everything comes from environment variables.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Look for .env in the project root (one level up from backend/)
    load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
except ImportError:
    pass


class Settings:
    # Database
    DB_HOST = os.environ.get("CI_DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("CI_DB_PORT", 3306))
    DB_USER = os.environ.get("CI_DB_USER", "root")
    DB_PASSWORD = os.environ.get("CI_DB_PASSWORD", "")
    DB_NAME = os.environ.get("CI_DB_NAME", "customer_intelligence")

    # GenAI
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # ML model artifacts (produced by the patched ML scripts)
    ML_MODEL_DIR = Path(
        os.environ.get("ML_MODEL_DIR", Path(__file__).resolve().parent.parent.parent.parent / "Machine_Learning" / "ml_output" / "models")
    )

    # CORS — restrict to your local React dev server by default
    ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:3000"
    ).split(",")
    if origin.strip()
]

    # API behavior
    DB_QUERY_TIMEOUT_SECONDS = int(os.environ.get("DB_QUERY_TIMEOUT_SECONDS", 15))


settings = Settings()
