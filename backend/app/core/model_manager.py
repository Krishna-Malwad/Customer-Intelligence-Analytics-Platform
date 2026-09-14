"""
models/model_manager.py
=========================
Loads all trained ML artifacts ONCE, when the FastAPI app starts, and
keeps them in memory for the lifetime of the process. Endpoints call
into this manager instead of retraining anything.

Expects these files to exist (created by the patched ML scripts —
see model_persistence_patch.py):
    Machine_Learning/ml_output/models/segmentation_model.joblib
    Machine_Learning/ml_output/models/clv_model.joblib
    Machine_Learning/ml_output/models/retention_model.joblib
    Machine_Learning/ml_output/models/co_occurrence.joblib

If a file is missing, that model's predictions are reported as
unavailable rather than faked — see each service function for how
this is surfaced to the API response.
"""

import logging
from pathlib import Path

import joblib

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    def __init__(self):
        self.segmentation = None  # {"kmeans": ..., "scaler": ...}
        self.clv_pipeline = None
        self.retention_pipeline = None
        self.co_occurrence = None
        self.load_status = {}

    def load_all(self):
        model_dir = Path(settings.ML_MODEL_DIR)
        self._load_one("segmentation", model_dir / "segmentation_model.joblib", "segmentation")
        self._load_one("clv_pipeline", model_dir / "clv_model.joblib", "clv_pipeline")
        self._load_one("retention_pipeline", model_dir / "retention_model.joblib", "retention_pipeline")
        self._load_one("co_occurrence", model_dir / "co_occurrence.joblib", "co_occurrence")
        logger.info("Model load status: %s", self.load_status)

    def _load_one(self, attr_name, path: Path, status_key: str):
        if path.exists():
            try:
                setattr(self, attr_name, joblib.load(path))
                self.load_status[status_key] = "loaded"
                logger.info("Loaded %s from %s", status_key, path)
            except Exception as e:
                self.load_status[status_key] = f"failed: {e}"
                logger.error("Failed to load %s: %s", status_key, e)
        else:
            self.load_status[status_key] = "missing (run model_persistence_patch.py steps first)"
            logger.warning("Model artifact not found: %s", path)


# Single shared instance, populated at app startup (see main.py's startup event)
model_manager = ModelManager()
