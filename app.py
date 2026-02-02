"""
Continuum API - FastAPI Application (Audit-Aligned Demo Version)
---------------------------------------------------------------
This version:
- Keeps your existing Z1Pipeline intact
- Surfaces repairer audit truth to frontend
- Makes LLM / gate / fallback fully visible & honest
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import os
import math
import time
from datetime import datetime, timezone

from pipeline.z1_pipeline import Z1Pipeline
from logger import DataLogger, GitHubBackup

# -------------------- Logging --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("continuum-api")

# -------------------- FastAPI App --------------------
app = FastAPI(
    title="Continuum API",
    description="Tone rhythm detection and repair for conversational AI",
    version="2.2.0-demo",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = None
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


@app.on_event("startup")
async def startup_event():
    global pipeline, data_logger, github_backup
    logger.info("🚀 Starting Continuum API (Demo)...")

    pipeline = Z1Pipeline(debug=False)
    data_logger = DataLogger(log_dir="logs")

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    if token and repo:
        github_backup = GitHubBackup(log_dir="logs")
        github_backup.restore()
    else:
        github_backup = None

    logger.info("✅ API ready")


# -------------------- Models --------------------
class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


class AnalyzeResponse(BaseModel):
    original: str
    freq_type: str
    mode: str
    confidence_final: float
    confidence_classifier: Optional[float] = None
    scenario: str
    repaired_text: Optional[str] = None
    repair_note: Optional[str] = None
    audit: Dict[str, Any]


# -------------------- Endpoint --------------------
@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")

    t0 = time.time()

    result = pipeline.process(request.text)

    if result.get("error"):
        raise HTTPException(400, result.get("reason"))

    original = result.get("original", request.text)
    freq_type = result.get("freq_type", "Unknown")

    conf_obj = result.get("confidence") or {}
    confidence_final = _safe_conf(conf_obj.get("final", 0.0))
    confidence_classifier = _safe_conf(conf_obj.get("classifier", 0.0))

    mode_raw = result.get("mode") or "no-op"
    mode = mode_raw.lower()
    if mode not in {"repair", "suggest", "no-op"}:
        mode = "no-op"

    out_obj = result.get("output") or {}
    scenario = out_obj.get("scenario", "unknown")
    repaired_text = out_obj.get("repaired_text")
    repair_note = out_obj.get("repair_note")

    # ---- IMPORTANT: audit merge ----
    repairer_audit = out_obj.get("audit") if isinstance(out_obj, dict) else {}
    latency_ms = int((time.time() - t0) * 1000)

    audit = {
        "server_time_utc": _utc_now(),
        "latency_ms": latency_ms,
        "mode": mode,
        "freq_type": freq_type,
        "scenario": scenario,
        "confidence_final": confidence_final,
        "repairer": repairer_audit or {},
    }

    # no-op must be transparent
    if mode == "no-op":
        repaired_text = original
        repair_note = "Tone is already within a safe range. Transparent pass-through."

    # logging (best-effort)
    if data_logger:
        try:
            data_logger.log_analysis(
                input_text=original,
                output_result=result,
                metadata={
                    "mode": mode,
                    "freq_type": freq_type,
                    "confidence_final": confidence_final,
                },
            )
        except Exception:
            pass

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