# Continuum 對客戶版（外部版）v1.0

> 文件性質：對外產品說明（可用於客戶簡報、採購評估、法務初審）  
> 版本：v1.0  
> 適用範圍：Continuum Output Governance Layer

---

## 1) 一句話定義

**Continuum 是生成式 AI 的發言權治理層（Output Governance Layer）。**

Continuum 的核心價值不是讓模型「更會回答」，  
而是在高風險語境中，決定 AI 是否應該繼續主導發言。

---

## 2) Continuum 解決的問題

在高信任對話場景（如心理健康、醫療、金融、客服、陪伴）中，  
風險常來自「AI 在不該主導時仍持續主導」。

典型風險：
- 過度安慰（Over-comforting）
- 越權引導（Over-guiding）
- 非請求式說教（Unsolicited coaching）

Continuum 的目標是降低上述風險，提升對話治理可控性與可稽核性。

---

## 3) 三態治理決策（唯一對外決策）

Continuum 對每一次輸出，僅產生一個治理決策：

### 🟢 ALLOW（透明通行）
- 語境穩定，AI 保有發言權
- 系統不做額外干預

### 🟡 GUIDE（降權治理）
- 偵測到風險，AI 不應主導對話
- 系統啟動最低風險行為策略（例如回聲、保守改寫、holding space）
- 重點是「權限被降低」，不是追求文案華麗度

### 🔴 BLOCK（強制攔截）
- 偵測到不可接受風險
- 原始輸出中止，轉交安全流程

---

## 4) 產品邊界（Hard Boundaries）

Continuum **不是**：
- 情緒陪伴 AI
- 心理治療或醫療判斷工具
- Prompt 優化器
- 語氣修辭工具

Continuum 不主張「更像人」，  
只主張「更可控的發言權配置」。

---

## 5) 治理保證（Governance Guarantees）

1. **No Viewpoint Censorship**  
   不做立場/觀點審查；僅做風險邊界與發言權治理。

2. **No Model Alteration**  
   不改動客戶基礎模型權重；作為輸出端治理層整合。

3. **No Intent Guessing**  
   不宣稱解讀隱含意圖；以可觀測語境訊號做決策。

4. **Privacy-first Logging**  
   不以原始用戶文本作為審計落地內容；  
   使用可稽核證據（如 decision、風險訊號、指紋化資訊）進行治理追蹤。

---

## 6) 外部 API 契約（摘要）

核心分析端點：

`POST /api/v1/analyze`

回應重點欄位（摘要）：
- `decision_state`：`ALLOW` / `GUIDE` / `BLOCK`
- `freq_type`：風險類型
- `confidence_final`：治理判斷信心
- `scenario`：場景標記
- `repaired_text`：治理後輸出（若適用）
- `privacy_guard_ok`：隱私防線狀態

運維端點（供企業監控）：
- `/api/v1/status`
- `/api/v1/ops/metrics`（決策分佈、延遲分位、使用率等）

---

## 7) 可觀測與可稽核能力（面向企業）

Continuum 提供可監控指標，用於營運與風險治理：
- 決策分佈（ALLOW/GUIDE/BLOCK）
- 延遲指標（p50/p95/p99）
- LLM 使用率
- 風險攔截率（如 OOS hit rate）

這些指標可用於：
- 合規稽核
- 風險委員會回報
- 供應商治理 KPI

---

## 8) 法務安全措辭（對外可用）

可用措辭（建議）：
- 「Continuum 是輸出端治理層，不是對話模型本體。」
- 「Continuum 提供可稽核的三態治理決策。」
- 「Continuum 用於降低越權輸出風險，非臨床判斷系統。」

避免措辭（不建議）：
- 「Continuum 保證 100% 防止所有風險」
- 「Continuum 可理解使用者真實意圖」
- 「Continuum 提供心理治療/醫療建議」

---

## 9) 導入方式（客戶視角）

Continuum 可作為現有模型的外掛治理層導入，  
不要求替換客戶既有大模型策略。

典型導入流程：
1. 接入分析端點
2. 依 `decision_state` 套用對應治理策略
3. 用 `/api/v1/ops/metrics` 建立監控與報表

---

## 10) 聲明

本文件為產品外部說明，  
不構成醫療、法律或投資建議。  
最終合約條款以雙方簽署版本為準。

