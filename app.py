# app.py
"""
Continuum API - Hugging Face Spaces Compatible App
--------------------------------------------------
PATCH:
- ✅ usage uses default_factory (avoid mutable default)
- ✅ timing: api_total / pipeline_total / server_overhead (truthful)
- ✅ does NOT treat length_too_short as an error (pipeline now returns error=False)
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("continuum-api")

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


def _none_if_empty(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    if isinstance(s, str) and s.strip() == "":
        return None
    return s


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
            github_backup = None
    else:
        github_backup = None

    logger.info("✅ Startup complete")
    yield
    logger.info("🧹 Shutdown complete")


app = FastAPI(
    title="Continuum API",
    description="AI conversation risk governance (output-side)",
    version="2.2.4-hf",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class AnalyzeResponse(BaseModel):
    original: str
    freq_type: str
    mode: str
    confidence_final: float
    confidence_classifier: Optional[float] = None
    scenario: str
    repaired_text: Optional[str] = None
    repair_note: Optional[str] = None

    raw_ai_output: Optional[str] = None

    llm_used: Optional[bool] = None
    cache_hit: Optional[bool] = None
    model: str = ""

    # ✅ no mutable default
    usage: Dict[str, Any] = Field(default_factory=dict)

    output_source: Optional[str] = None

    audit: Dict[str, Any]
    metrics: Optional[Dict[str, Any]] = None


@app.get("/")
async def root():
    return {"name": "Continuum API", "status": "running", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {
        "pipeline_ready": pipeline is not None,
        "logger_ready": data_logger is not None,
        "github_backup_enabled": github_backup is not None,
        "time": _utc_now(),
    }


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")

    t_api_start = time.time()
    result = pipeline.process(req.text)

    # ✅ only treat as error when pipeline truly errors
    if result.get("error") is True:
        raise HTTPException(400, result.get("reason", "pipeline_error"))

    original = result.get("original", req.text)
    freq_type = result.get("freq_type", "Unknown")
    mode = (result.get("mode") or "no-op").lower()

    conf_obj = result.get("confidence") or {}
    confidence_final = _safe_conf(conf_obj.get("final", result.get("confidence_final", 0.0)))
    confidence_classifier = _safe_conf(conf_obj.get("classifier", result.get("confidence_classifier", 0.0)))

    out = result.get("output") or {}
    scenario = out.get("scenario", result.get("scenario", "unknown"))
    repaired_text = out.get("repaired_text", result.get("repaired_text"))
    repair_note = out.get("repair_note", result.get("repair_note"))

    raw_ai_output = (
        out.get("raw_ai_output")
        or out.get("llm_raw_output")
        or out.get("llm_raw_response")
        or result.get("raw_ai_output")
    )
    raw_ai_output = _none_if_empty(raw_ai_output)

    llm_used = result.get("llm_used", None)
    cache_hit = result.get("cache_hit", None)
    model_name = result.get("model", "") or ""
    usage = result.get("usage", {}) if isinstance(result.get("usage", {}), dict) else {}
    output_source = result.get("output_source", None)

    # ---- Audit: pipeline truth + API timing decomposition ----
    audit_top = result.get("audit") if isinstance(result.get("audit"), dict) else {}
    audit = dict(audit_top)

    audit.setdefault("timing_ms", {})
    if not isinstance(audit.get("timing_ms"), dict):
        audit["timing_ms"] = {}

    api_total = int((time.time() - t_api_start) * 1000)

    # pipeline_total = audit.timing_ms.total if pipeline provided it, else processing_time_ms if present
    pipeline_total = None
    if isinstance(audit.get("timing_ms"), dict) and isinstance(audit["timing_ms"].get("total"), int):
        pipeline_total = audit["timing_ms"]["total"]
    elif isinstance(result.get("processing_time_ms"), int):
        pipeline_total = result.get("processing_time_ms")

    audit["timing_ms"]["api_total"] = api_total
    if isinstance(pipeline_total, int):
        audit["timing_ms"]["pipeline_total"] = pipeline_total
        audit["timing_ms"]["server_overhead"] = max(0, api_total - pipeline_total)
    else:
        audit["timing_ms"]["pipeline_total"] = None
        audit["timing_ms"]["server_overhead"] = None

    audit["server_time_utc"] = _utc_now()

    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else None

    return AnalyzeResponse(
        original=original,
        freq_type=freq_type,
        mode=mode,
        confidence_final=confidence_final,
        confidence_classifier=confidence_classifier,
        scenario=scenario,
        repaired_text=repaired_text,
        repair_note=repair_note,
        raw_ai_output=raw_ai_output,

        llm_used=llm_used,
        cache_hit=cache_hit,
        model=model_name,
        usage=usage,
        output_source=output_source,

        audit=audit,
        metrics=metrics,
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, log_level="info")