"""Z1 API - Auto-sync from z1_mvp + GitHub data backup"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging
import os
from datetime import datetime
import asyncio

# Auto-copied by GitHub Actions
from pipeline.z1_pipeline import Z1Pipeline
from logger import DataLogger, GitHubBackup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Z1 Tone Firewall API",
    version="1.0.0",
    description="AI-powered tone detection and repair for complete sentences"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize
try:
    pipeline = Z1Pipeline(config_path='configs/settings.yaml', debug=False)
    data_logger = DataLogger()
    gh_backup = GitHubBackup()
    logger.info("✅ Pipeline & Logger & Backup ready")
except Exception as e:
    logger.error(f"❌ Init failed: {e}")
    pipeline = None
    data_logger = None
    gh_backup = None

# ===== Data Models =====
class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

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

# ===== Language Detection =====
def detect_language(text: str) -> str:
    """
    Detect primary language of text
    
    Args:
        text: Text to detect
    
    Returns:
        'zh' (Chinese) or 'en' (English)
    """
    # Keep only letters and Chinese characters
    clean_text = ''.join(c for c in text if c.isalpha() or '\u4e00' <= c <= '\u9fff')
    
    if not clean_text:
        return 'zh'  # Default to Chinese
    
    # Count Chinese characters
    chinese_chars = sum(1 for char in clean_text if '\u4e00' <= char <= '\u9fff')
    
    # If over 30% Chinese characters → classify as Chinese
    if len(clean_text) == 0:
        return 'zh'
    
    chinese_ratio = chinese_chars / len(clean_text)
    return 'zh' if chinese_ratio > 0.3 else 'en'

# ===== Bilingual Contextual Response =====
def generate_contextual_response(text: str, freq_type: str, confidence: float) -> tuple[str, str]:
    """
    Generate contextual response based on text length, confidence, and language
    
    Args:
        text: Original text
        freq_type: Tone type
        confidence: Confidence score
    
    Returns:
        (repaired_text, repair_note)
    """
    text_len = len(text.strip())
    lang = detect_language(text)
    
    # Bilingual message templates
    messages = {
        'short': {
            'zh': f"此訊息較短（{text_len} 字）。Z1 專注於完整句子（建議 15 字以上）的語氣分析，以獲得最準確的判斷結果。",
            'en': f"This message is short ({text_len} characters). Z1 focuses on complete sentences (15+ characters recommended) for accurate tone analysis."
        },
        'medium_low_conf': {
            'zh': f"語氣判斷信心度 {int(confidence*100)}%。Z1 在完整、明確的句子上表現最佳，建議將表達擴充為更完整的句子以獲得更精準的分析。",
            'en': f"Tone detection confidence: {int(confidence*100)}%. Z1 performs best on complete, clear sentences. Consider expanding your expression for more accurate analysis."
        },
        'unknown': {
            'zh': "此訊息的語氣特徵不明確。Z1 專注於完整句子的語氣分析，建議使用更具體、完整的表達方式以獲得準確判斷。",
            'en': "Tone characteristics unclear. Z1 focuses on complete sentence analysis. Use more specific and complete expressions for accurate detection."
        },
        'low_conf': {
            'zh': f"系統判斷信心度 {int(confidence*100)}%。建議人工確認是否需要調整表達方式。",
            'en': f"System confidence: {int(confidence*100)}%. Manual review recommended to determine if expression adjustment is needed."
        }
    }
    
    # Case 1: Short message (<10 chars)
    if text_len < 10:
        return (text, messages['short'][lang])
    
    # Case 2: Medium length + low confidence (10-20 chars, <0.4)
    elif text_len < 20 and confidence < 0.4:
        return (text, messages['medium_low_conf'][lang])
    
    # Case 3: Unknown type
    elif freq_type == "Unknown":
        return (text, messages['unknown'][lang])
    
    # Case 4: General low confidence (<0.3)
    elif confidence < 0.3:
        return (text, messages['low_conf'][lang])
    
    # Should not reach here
    return (text, None)

# ===== Background Task: Periodic Backup =====
async def periodic_backup():
    """Backup to GitHub every hour"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            if gh_backup:
                gh_backup.backup()
                logger.info("✅ Logs backed up to GitHub")
        except Exception as e:
            logger.error(f"⚠️ Backup failed: {e}")

@app.on_event("startup")
async def startup_event():
    """Restore previous logs on startup"""
    if gh_backup:
        try:
            gh_backup.restore()
            logger.info("✅ Previous logs restored")
        except:
            logger.info("ℹ️ No previous logs, starting fresh")
    
    # Start backup task
    asyncio.create_task(periodic_backup())

# ===== API Endpoints =====
@app.get("/")
async def root():
    return {
        "message": "Z1 Tone Firewall API",
        "version": "1.0.0",
        "model": "claude-haiku-4-5-20251001",
        "focus": "Complete sentence tone analysis (15+ characters recommended)",
        "languages": ["zh", "en"],
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy" if pipeline else "unhealthy",
        "pipeline": pipeline is not None,
        "logger": data_logger is not None,
        "backup": gh_backup is not None
    }

@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze tone (complete sentences recommended for best results)"""
    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")
    
    try:
        # Detect language
        detected_lang = detect_language(request.text)
        
        # Execute analysis
        result = pipeline.process(request.text)
        
        if result.get("error"):
            raise HTTPException(400, result.get("reason"))
        
        # Get basic results
        freq_type = result["freq_type"]
        confidence = result["confidence"]["final"]
        repaired_text = result["output"].get("repaired_text")
        repair_note = None
        
        # Handle Unknown or low confidence cases
        if freq_type == "Unknown" or confidence < 0.3:
            repaired_text, repair_note = generate_contextual_response(
                text=request.text,
                freq_type=freq_type,
                confidence=confidence
            )
            logger.info(f"ℹ️ Contextual response: len={len(request.text)}, lang={detected_lang}, type={freq_type}, conf={confidence:.2f}")
        
        # Log data
        log_id = None
        if data_logger:
            try:
                log_entry = data_logger.log(
                    input_text=request.text,
                    output_result=result,
                    metadata={
                        'model': 'claude-haiku-4-5-20251001',
                        'api_version': 'v1',
                        'detected_language': detected_lang,
                        'truncated': result.get('truncated', False),
                        'low_confidence': confidence < 0.3,
                        'text_length': len(request.text),
                        'has_repair_note': repair_note is not None
                    }
                )
                log_id = log_entry.get('timestamp')
            except Exception as e:
                logger.error(f"⚠️ Log failed: {e}")
        
        # Return response
        return AnalyzeResponse(
            original=result["original"],
            freq_type=freq_type,
            confidence=confidence,
            scenario=result["output"]["scenario"],
            repaired_text=repaired_text,
            repair_note=repair_note,
            log_id=log_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Submit user feedback"""
    if not data_logger:
        raise HTTPException(503, "Logger not ready")
    
    try:
        data_logger.log_feedback(
            log_id=feedback.log_id,
            accuracy=feedback.accuracy,
            helpful=feedback.helpful,
            accepted=feedback.accepted
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Feedback error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/v1/stats")
async def get_stats():
    """Get usage statistics"""
    if not data_logger:
        raise HTTPException(503, "Logger not ready")
    
    try:
        return data_logger.get_stats()
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/v1/backup")
async def manual_backup():
    """Trigger manual backup to GitHub"""
    if not gh_backup:
        raise HTTPException(503, "Backup not ready")
    
    try:
        gh_backup.backup()
        
        gh_repo = os.environ.get('GH_REPO', 'unknown')
        
        return {
            "status": "ok",
            "message": "Backup completed",
            "verify_url": f"https://github.com/{gh_repo}"
        }
    except Exception as e:
        logger.error(f"❌ Manual backup failed: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/v1/test-backup")
async def test_backup():
    """Test GitHub backup functionality (comprehensive test)"""
    try:
        # Create test data
        test_result = {
            'original': 'Manual backup test from API',
            'freq_type': 'Test',
            'confidence': {'final': 0.99},
            'output': {
                'scenario': 'api_test',
                'repaired_text': 'This is a test message',
                'mode': 'test'
            },
            'rhythm': {
                'total': 1,
                'speed_index': 0.5,
                'emotion_rate': 0.0
            }
        }
        
        # Log test data
        if data_logger:
            log_entry = data_logger.log(
                input_text='Manual backup test from API',
                output_result=test_result,
                metadata={
                    'test': True,
                    'source': 'api_test_endpoint',
                    'timestamp': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Test data logged: {log_entry['timestamp']}")
        else:
            raise HTTPException(503, "Logger not ready")
        
        # Execute backup
        if gh_backup:
            gh_backup.backup()
            logger.info("✅ Test backup completed")
        else:
            raise HTTPException(503, "Backup not configured")
        
        # Prepare response
        gh_repo = os.environ.get('GH_REPO', 'unknown')
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        return {
            "status": "success",
            "message": "Backup test completed successfully",
            "test_data_logged": True,
            "backup_executed": True,
            "verify_url": f"https://github.com/{gh_repo}",
            "instructions": [
                "1. Visit the URL above",
                "2. Check for latest commit (should be within last minute)",
                f"3. Look for file: analysis_{date_str}.jsonl",
                "4. Open the file and verify it contains test data",
                "5. Search for 'api_test_endpoint' in the file"
            ],
            "expected_content": {
                "source": "api_test_endpoint",
                "text": "Manual backup test from API",
                "freq_type": "Test"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test backup failed: {e}")
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 7860))
    )
```

---
