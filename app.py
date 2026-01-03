"""
Continuum API - HF-safe version
RIN Protocol — Tone Rhythm Repair Module
Auto-sync from z1_mvp + manual GitHub data backup
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import logging
import os
from datetime import datetime

# Auto-copied by GitHub Actions
from pipeline.z1_pipeline import Z1Pipeline
from logger import DataLogger, GitHubBackup

# ------------------------
# App & Logging
# ------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Continuum API",
    version="1.0.0",
    description="RIN Protocol — Tone Rhythm Repair Module. AI-powered tone detection and repair for complete sentences"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# ... (中間部分保持不變)
# ------------------------

def generate_contextual_response(
    text: str, freq_type: str, confidence: float
) -> tuple[str, str]:

    text_len = len(text.strip())
    lang = detect_language(text)

    messages = {
        "short": {
            "zh": f"此訊息較短（{text_len} 字）。Continuum 專注於完整句子（建議 15 字以上）的語氣分析。",
            "en": f"This message is short ({text_len} characters). Continuum works best on complete sentences (15+).",
        },
        "medium_low_conf": {
            "zh": f"語氣判斷信心度 {int(confidence*100)}%。建議使用更完整的表達。",
            "en": f"Tone confidence {int(confidence*100)}%. Consider expanding your expression.",
        },
        "unknown": {
            "zh": "語氣特徵不明確，建議更具體的完整句子。",
            "en": "Tone unclear. More complete expressions recommended.",
        },
        "low_conf": {
            "zh": f"信心度 {int(confidence*100)}%，建議人工確認。",
            "en": f"Confidence {int(confidence*100)}%. Manual review recommended.",
        },
    }

    if text_len < 10:
        return text, messages["short"][lang]
    if text_len < 20 and confidence < 0.4:
        return text, messages["medium_low_conf"][lang]
    if freq_type == "Unknown":
        return text, messages["unknown"][lang]
    if confidence < 0.3:
        return text, messages["low_conf"][lang]

    return text, None

# ------------------------
# API Endpoints
# ------------------------

@app.get("/")
async def root():
    return {
        "message": "Continuum API — RIN Protocol",
        "product": "Continuum",
        "version": "1.0.0",
        "languages": ["zh", "en"],
        "docs": "/docs",
    }

# ... (其他部分保持不變)
