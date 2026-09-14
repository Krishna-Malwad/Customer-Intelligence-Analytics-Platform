"""
app/main.py
============
FastAPI application entry point.

Run locally (from the backend/ directory):
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.model_manager import model_manager
from app.api.routes import health, customers, ml, analytics, genai, data_quality

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading ML model artifacts...")
    model_manager.load_all()
    logger.info("Startup complete. Model status: %s", model_manager.load_status)
    yield


app = FastAPI(
    title="Customer Intelligence API",
    description="Backend for the Olist Customer Intelligence Analytics Platform. "
                 "Serves real database queries and pre-trained ML model predictions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "Customer Intelligence API", "status": "running", "docs": "/docs"}


app.include_router(health.router)
app.include_router(customers.router)
app.include_router(ml.router)
app.include_router(analytics.router)
app.include_router(genai.router)
app.include_router(data_quality.router)
