---
title: Continuum API
emoji: 💎
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "{{sdkVersion}}"
app_file: app.py
pinned: false
---

# Continuum API — RIN Protocol

**Tone Misalignment Firewall**  
語氣錯頻辨識 × 節奏修復 API

Continuum is not a sentiment analyzer.  
It is a **tone safety layer** designed to prevent conversational breakdowns caused by misaligned tone, rhythm, or pressure.

---

## 🧠 What This System Does (Plain Language)

Given a single sentence, Continuum will:

1. **Analyze rhythm & emotional pressure**
2. **Classify tone misalignment type**  
   (Anxious / Cold / Sharp / Blur / Pushy)
3. **Estimate confidence of the judgment**
4. **Decide whether to:**
   - repair the tone
   - suggest adjustment
   - or leave it untouched

This prevents over-correction and preserves the user’s original intent.

---

## 🚫 What This System Explicitly Does NOT Do

- ❌ No sentiment scoring (positive / negative)
- ❌ No intent guessing
- ❌ No hidden-meaning inference
- ❌ No psychological diagnosis
- ❌ No multi-turn memory (single-sentence only)

These are **Phase 2 features** and intentionally disabled in MVP.

---

## 🏗️ Architecture Overview

Input Text
↓
Normalization & Length Gate
↓
Rhythm Analysis (speed / emotion / pause)
↓
Tone Classification (rule-based + margin confidence)
↓
Confidence Calibration (rhythm-aware)
↓
Router
├── repair     (high confidence)
├── suggest    (medium confidence)
└── no-op      (safe / neutral)
↓
Output

---

## 🎯 Supported Tone Types (MVP Scope)

- **Anxious** — help-seeking, overwhelmed, uncertainty
- **Cold** — detached, withdrawn, disengaged
- **Sharp** — harsh, commanding, high-pressure
- **Blur** — vague, ambiguous, unclear
- **Pushy** — pressing, demanding, urgency-driven

> Neutral / safe tone is explicitly supported and will not be modified.

---

## 🧪 Output Modes

- **repair**  
  → Tone is adjusted while preserving meaning

- **suggest**  
  → Original text kept, guidance provided

- **no-op**  
  → Tone is already safe; no change applied

---

## 🚀 API Endpoints

### Health Check
```bash
GET /health

Analyze Single Sentence

POST /api/v1/analyze
{
  "text": "your input text"
}

Response Example

{
  "freq_type": "Anxious",
  "confidence": {
    "final": 0.73
  },
  "mode": "repair",
  "output": {
    "repaired_text": "I'm here with you. We can take this step by step."
  }
}


⸻

🧩 Design Philosophy
	•	Explainable over powerful
	•	Predictable over clever
	•	Safety gates over maximal recall
	•	User voice preserved

Continuum is designed as a pre-LLM safety layer for empathic systems, not a replacement for them.

⸻

🔄 Sync & Deployment

This repo automatically syncs pipeline, core logic, and configs from:

🔗 https://github.com/Rin-Nomia/z1_mvp

Do not edit synced files directly.

⸻

🛣️ Phase 2 (Out of Scope)
	•	Multi-label tone blending
	•	Hidden meaning inference
	•	Relationship / context awareness
	•	Multi-turn conversation repair
	•	Culture-specific tone policies

These will be introduced behind explicit feature gates.

⸻

🔗 Links
	•	z1_mvp: https://github.com/Rin-Nomia/z1_mvp
	•	Playground: https://rin-nomia.github.io/continuum-api/playground.html
	•	API Docs: /docs

⸻

RIN Protocol — Continuum
Tone safety before intelligence
Built by Rin Nomia

---
