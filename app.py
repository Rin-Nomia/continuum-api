"""Z1 API - 自動從 z1_mvp 同步"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging
import os

# 這些會被 GitHub Actions 自動複製過來
from pipeline.z1_pipeline import Z1Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Z1 Tone Firewall API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    pipeline = Z1Pipeline(config_path='configs/settings.yaml', debug=False)
    logger.info("✅ Pipeline ready")
except Exception as e:
    logger.error(f"❌ Pipeline failed: {e}")
    pipeline = None

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

class AnalyzeResponse(BaseModel):
    original: str
    freq_type: str
    confidence: float
    scenario: str
    repaired_text: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Z1 API", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy" if pipeline else "unhealthy"}

@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")
    try:
        result = pipeline.process(request.text)
        if result.get("error"):
            raise HTTPException(400, result.get("reason"))
        return AnalyzeResponse(
            original=result["original"],
            freq_type=result["freq_type"],
            confidence=result["confidence"]["final"],
            scenario=result["output"]["scenario"],
            repaired_text=result["output"].get("repaired_text")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
