---
title: Trust Layer
emoji: 🛡️
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "{{sdkVersion}}"
app_file: app.py
pinned: false
---

# Trust Layer — 客服 AI 承諾邊界治理層

AI 客服回答問題已是基本能力。  
但 AI 在高壓對話裡會亂給承諾——  
用戶拿著 AI 說過的話要求兌現，企業不認帳，信任崩潰。  

Trust Layer 在對話裡即時偵測六種高風險狀態與未授權承諾，  
輸出 ALLOW / GUIDE / BLOCK 治理決策，並保留可稽核記錄。  
讓你的 AI 客服，值得被信任。  

---

## 三模式治理

- **Sense（ALLOW）**：一般互動，無需介入，記錄存檔
- **Guide（GUIDE）**：風險互動，介入引導，限制承諾範圍
- **Block（BLOCK）**：危機互動，攔截輸出，轉交人工處理

---

## 系統定位

Trust Layer 不替換既有客服 AI。  
它是在高風險互動時介入的治理層，提供：

- 危機訊號攔截（例如自傷/危機語句）
- 承諾邊界偵測（退款、折扣、賠償、法律保證、合約變更）
- 語氣與壓力風險治理（高壓、推進、模糊風險）

---

## API 回傳核心欄位

`POST /api/v1/analyze` 會固定回傳：

- `decision_state`：`ALLOW` / `GUIDE` / `BLOCK`
- `governance_mode`：`Sense` / `Guide` / `Block`
- `intervention_reason_code`：介入原因碼（ALLOW 時為 `null`）
- `risk_category`：標準化風險分類
- `risk_label`：人類可讀風險標籤

詳見：

- [docs/CONTRACT_V1.md](docs/CONTRACT_V1.md)
- [docs/EVIDENCE_SCHEMA_V1.md](docs/EVIDENCE_SCHEMA_V1.md)
- [docs/RISK_TAXONOMY_V1.md](docs/RISK_TAXONOMY_V1.md)

---

## 快速連結

- API 文件：`/docs`
- 狀態頁：`/status`
- Playground：`/playground`
- C3 Dashboard 說明：[docs/C3_COMMAND_CENTER_V1.md](docs/C3_COMMAND_CENTER_V1.md)
- 快速接入：[QUICKSTART.md](QUICKSTART.md)

---

## 邊界聲明

Trust Layer 能偵測的是有明確語言訊號的高風險對話。  
它不保證攔截所有承諾風險，不替代法務審查，不提供法律建議。  
