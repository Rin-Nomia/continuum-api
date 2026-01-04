"""
Continuum API - FastAPI Application
Tone rhythm detection and repair API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging
import os

from pipeline.z1_pipeline import Z1Pipeline
from logger import DataLogger, GitHubBackup

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== FastAPI App ====================
app = FastAPI(
    title="Continuum API",
    description="Tone rhythm detection and repair for conversational AI",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Global Instances ====================
pipeline = None
data_logger = None
github_backup = None

@app.on_event("startup")
async def startup_event():
    """Initialize pipeline and logger on startup"""
    global pipeline, data_logger, github_backup
    
    logger.info("🚀 Starting Continuum API...")
    
    # Initialize pipeline
    try:
        logger.info("📦 Initializing Z1 Pipeline...")
        pipeline = Z1Pipeline(debug=False)
        logger.info("✅ Pipeline ready")
    except Exception as e:
        logger.error(f"❌ Pipeline initialization failed: {e}")
        pipeline = None
    
    # Initialize data logger
    try:
        logger.info("📊 Initializing Data Logger...")
        data_logger = DataLogger(log_dir='logs')
        logger.info("✅ Data Logger ready")
    except Exception as e:
        logger.warning(f"⚠️ Data Logger initialization failed: {e}")
        data_logger = None
    
    # Initialize GitHub backup (optional)
    try:
        if os.environ.get('GH_TOKEN') and os.environ.get('GH_REPO'):
            logger.info("📦 Initializing GitHub Backup...")
            github_backup = GitHubBackup(log_dir='logs')
            github_backup.restore()
            logger.info("✅ GitHub Backup ready")
    except Exception as e:
        logger.warning(f"⚠️ GitHub Backup initialization failed: {e}")
        github_backup = None
    
    logger.info("=" * 50)
    logger.info("🎉 Continuum API is ready!")
    logger.info("=" * 50)

# ==================== Request/Response Models ====================

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class AnalyzeResponse(BaseModel):
    original: str
    freq_type: str
    confidence: float
    scenario: str
    repaired_text: Optional[str] = None
    repair_note: Optional[str] = None
    log_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    log_id: str
    accuracy: int = Field(..., ge=1, le=5)
    helpful: int = Field(..., ge=1, le=5)
    accepted: bool

# ==================== Helper Functions ====================

def generate_contextual_response(text: str, freq_type: str, confidence: float):
    """Generate contextual response for low confidence or unknown type"""
    if freq_type == "Unknown":
        return (
            text,
            "Unable to detect specific tone pattern. The text appears neutral or requires more context."
        )
    
    if confidence < 0.3:
        return (
            text,
            f"Low confidence detection ({confidence:.2f}). Suggested tone: {freq_type}. Please review manually."
        )
    
    return (text, None)

# ==================== API Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "pipeline_ready": pipeline is not None,
        "logger_ready": data_logger is not None,
        "backup_ready": github_backup is not None
    }

@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze tone (complete sentences recommended for best results)"""
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")
    
    try:
        # Process text
        result = pipeline.process(request.text)
        
        if result.get("error"):
            raise HTTPException(400, result.get("reason"))
        
        freq_type = result["freq_type"]
        confidence = result["confidence"]["final"]
        repaired_text = result["output"].get("repaired_text")
        repair_note = None
        
        # Handle low confidence or unknown type
        if freq_type == "Unknown" or confidence < 0.3:
            repaired_text, repair_note = generate_contextual_response(
                request.text, freq_type, confidence
            )
        
        # Log analysis
        log_id = None
        if data_logger:
            try:
                log = data_logger.log_analysis(
                    input_text=request.text,
                    output_result=result,
                    metadata={
                        "confidence": confidence,
                        "freq_type": freq_type,
                        "text_length": len(request.text),
                    },
                )
                log_id = log.get("timestamp")
            except Exception as log_error:
                logger.warning(f"⚠️ Logging failed: {log_error}")
        
        return AnalyzeResponse(
            original=result["original"],
            freq_type=freq_type,
            confidence=confidence,
            scenario=result["output"]["scenario"],
            repaired_text=repaired_text,
            repair_note=repair_note,
            log_id=log_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Analysis failed: {str(e)}")

@app.post("/api/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for an analysis"""
    if not data_logger:
        raise HTTPException(503, "Logger not available")
    
    try:
        data_logger.log_feedback(
            log_id=request.log_id,
            accuracy=request.accuracy,
            helpful=request.helpful,
            accepted=request.accepted
        )
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        logger.error(f"❌ Feedback error: {str(e)}")
        raise HTTPException(500, f"Failed to record feedback: {str(e)}")

@app.get("/api/v1/stats")
async def get_stats():
    """Get usage statistics"""
    if not data_logger:
        raise HTTPException(503, "Logger not available")
    
    try:
        stats = data_logger.get_stats()
        return stats
    except Exception as e:
        logger.error(f"❌ Stats error: {str(e)}")
        raise HTTPException(500, f"Failed to get stats: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Continuum API",
        "version": "2.0.0",
        "status": "active",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
