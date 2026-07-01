# CONTRACT_V1

## 1. 系統定位

Trust Layer 是客服 AI 的承諾邊界治理層，不替換現有客服 AI，只在高風險時刻介入。

---

## 2. 三層偵測架構

- 第一層：危機訊號偵測（用戶輸入）
- 第二層：承諾邊界偵測（AI 草稿輸出）
- 第三層：語氣風險偵測（用戶輸入）

---

## 3. 固定 API 回傳欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| decision_state | string | ALLOW / GUIDE / BLOCK |
| governance_mode | string | Sense / Guide / Block |
| intervention_reason_code | string or null | 介入原因代碼 |
| risk_category | string | 風險分類 |
| risk_label | string | 風險標籤（人類可讀） |

### API 回傳範例

**情境一：ALLOW（Sense）**

```json
{
  "decision_state": "ALLOW",
  "governance_mode": "Sense",
  "intervention_reason_code": null,
  "risk_category": "no_intervention",
  "risk_label": "一般互動"
}
```

**情境二：GUIDE（Guide）**

```json
{
  "decision_state": "GUIDE",
  "governance_mode": "Guide",
  "intervention_reason_code": "unauthorized_refund_commitment",
  "risk_category": "commitment_refund_discount",
  "risk_label": "未授權退款承諾"
}
```

**情境三：BLOCK（Block）**

```json
{
  "decision_state": "BLOCK",
  "governance_mode": "Block",
  "intervention_reason_code": "crisis_self_harm",
  "risk_category": "crisis_safety",
  "risk_label": "危機安全訊號"
}
```

---

## 4. 承諾風險分級表

| 風險類型 | 決策 | 說明 |
|---------|------|------|
| 退款承諾 | GUIDE | 限制回應，不強制轉人工 |
| 折扣承諾 | GUIDE | 限制回應，不強制轉人工 |
| 賠償承諾 | BLOCK | 攔截，強制轉人工 |
| 法律保證 | BLOCK | 攔截，強制轉人工 |
| 合約變更 | BLOCK | 攔截，強制轉人工 |

---

## 5. 隱私保護原則

- 不儲存原始對話內容
- 僅保留決策記錄（觸發原因、決策結果、時間戳）
- 客戶可選擇模式A（隱私優先）或模式B（法務追溯）

---

## 6. 系統邊界聲明

Trust Layer 能偵測的是有明確語言訊號的高風險對話。  
Trust Layer 不保證攔截所有承諾風險，不替代法務審查，不提供法律建議。

---

## 7. 版本資訊

CONTRACT_V1 — 2026年發布
