"""
Continuum API - Hugging Face Spaces Compatible App
--------------------------------------------------
Key points:
- Uses FastAPI lifespan (no deprecated on_event)
- Explicitly starts uvicorn on port 7860
- Keeps your pipeline / LLM / audit logic intact
"""

import os
import time
import math
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from pipeline.z1_pipeline import Z1Pipeline
from logger import DataLogger, GitHubBackup

# -------------------- Logging --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("continuum-api")

# -------------------- Globals --------------------
pipeline: Optional[Z1Pipeline] = None
data_logger: Optional[DataLogger] = None
github_backup: Optional[GitHubBackup] = None


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _safe_conf(v, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return default
        return max(0.0, min(1.0, x))
    except Exception:
        return default


# -------------------- Lifespan (HF-safe) --------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, data_logger, github_backup

    logger.info("🚀 Starting Continuum API (HF Space)")

    pipeline = Z1Pipeline(debug=False)
    data_logger = DataLogger(log_dir="logs")

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    if token and repo:
        try:
            github_backup = GitHubBackup(log_dir="logs")
            github_backup.restore()
            logger.info("📦 GitHub backup restored")
        except Exception as e:
            logger.warning(f"GitHub backup skipped: {e}")
    else:
        github_backup = None

    logger.info("✅ Startup complete")
    yield
    logger.info("🧹 Shutdown complete")


# -------------------- FastAPI App --------------------
app = FastAPI(
    title="Continuum API",
    description="Tone rhythm detection and repair for conversational AI",
    version="2.2.1-hf",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- Models --------------------
class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


class AnalyzeResponse(BaseModel):
    original: str
    freq_type: str
    mode: str
    confidence_final: float
    confidence_classifier: Optional[float]
    scenario: str
    repaired_text: Optional[str]
    repair_note: Optional[str]
    audit: Dict[str, Any]


# -------------------- Endpoints --------------------
@app.get("/")
async def root():
    return {
        "name": "Continuum API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {
        "pipeline_ready": pipeline is not None,
        "logger_ready": data_logger is not None,
        "time": _utc_now(),
    }


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")

    t0 = time.time()
    result = pipeline.process(req.text)

    if result.get("error"):
        raise HTTPException(400, result.get("reason"))

    original = result.get("original", req.text)
    freq_type = result.get("freq_type", "Unknown")

    conf = result.get("confidence") or {}
    confidence_final = _safe_conf(conf.get("final", 0.0))
    confidence_classifier = _safe_conf(conf.get("classifier", 0.0))

    mode = (result.get("mode") or "no-op").lower()
    out = result.get("output") or {}

    scenario = out.get("scenario", "unknown")
    repaired_text = out.get("repaired_text")
    repair_note = out.get("repair_note")

    if mode == "no-op":
        repaired_text = original
        repair_note = "Tone is within safe range. Transparent pass-through."

    audit = {
        "server_time_utc": _utc_now(),
        "latency_ms": int((time.time() - t0) * 1000),
        "mode": mode,
        "freq_type": freq_type,
        "confidence_final": confidence_final,
        "repairer": out.get("audit", {}),
    }

    return AnalyzeResponse(
        original=original,
        freq_type=freq_type,
        mode=mode,
        confidence_final=confidence_final,
        confidence_classifier=confidence_classifier,
        scenario=scenario,
        repaired_text=repaired_text,
        repair_note=repair_note,
        audit=audit,
    )


# -------------------- HF entrypoint --------------------
if __name__ == "__main__":
    # Hugging Face expects port 7860
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=7860,
        log_level="info",
    )