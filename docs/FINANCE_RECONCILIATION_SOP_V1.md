# FINANCE RECONCILIATION SOP V1

## 1. 文件目的

本 SOP 用於年度（或月度）商業對帳，確保：
- usage 摘要可追溯
- 簽章可驗證
- 帳務數字可重建

本 SOP 適用檔案：
- `logs/usage/<YYYY-MM>.summary.json`
- `logs/usage/<YYYY-MM>.summary.sig`

---

## 2. 前置條件

必備環境：
- `LOG_SALT`（必填）
- `USAGE_SIGNING_KEY`（建議與客戶專案隔離）

必備文件：
- 客戶授權檔（加密）
- 當期所有月度 usage 摘要與 .sig 檔

---

## 3. 月度對帳標準流程

### Step A：產生月度摘要

方式 1（API）：

```bash
POST /api/v1/billing/usage-summary?month=YYYY-MM
```

方式 2（自動）：
- 月切時系統自動封存上月摘要
- 關機時系統會補做當月摘要封存

輸出：
- `logs/usage/YYYY-MM.summary.json`
- `logs/usage/YYYY-MM.summary.sig`

---

### Step B：驗證簽章完整性

在工作區（z1_mvp）執行：

```bash
python scripts/verify_usage_summary_sig.py \
  --summary logs/usage/2026-02.summary.json \
  --sig logs/usage/2026-02.summary.sig \
  --key "$USAGE_SIGNING_KEY"
```

預期結果：
- 回傳 `VALID`

若為 `INVALID`：
1. 停止出帳
2. 重新匯出同月份摘要
3. 重新驗簽
4. 仍失敗則升級為安全事件

---

### Step C：寫入財務對帳表

從 `YYYY-MM.summary.json` 取值：
- `counts.analysis_count`
- `counts.feedback_count`
- `counts.total_events`

將每月數據匯入財務台帳，形成年度總計。

---

## 4. 年度對帳流程

1. 收齊 12 個月份的 `.summary.json` + `.sig`
2. 每月逐一驗簽（保留驗簽結果）
3. 匯總全年 total_events
4. 與合約額度、發票金額交叉核對
5. 封存「對帳證據包」供稽核

建議證據包結構：

```text
reconciliation/
├── 2026-01.summary.json
├── 2026-01.summary.sig
├── 2026-02.summary.json
├── 2026-02.summary.sig
├── ...
└── annual_reconciliation_2026.xlsx
```

---

## 5. 建議截圖清單（交付版）

> 以下為建議截圖項目，用於財務/法務留存。

1. API 匯出成功畫面（含 month 與 counts）
2. `logs/usage/` 目錄檔案清單（含 `.summary.json` 與 `.sig`）
3. 驗簽指令執行結果（`VALID`）
4. 年度彙總表（各月 total_events）
5. 發票與彙總表對照頁（最終核銷）

---

## 6. 異常處理規範

### Case 1：當月摘要不存在
- 先呼叫 `/api/v1/billing/usage-summary?month=YYYY-MM` 補生成

### Case 2：簽章驗證失敗
- 視為高優先異常，暫停出帳
- 進行重新匯出與二次驗簽

### Case 3：額度爭議
- 以 `.summary.json + .sig` 驗證後數據為準
- 追溯 `license_id` 與授權期限

---

## 7. 對帳治理原則

- 不使用 raw content 作為對帳依據
- 只使用 content-free usage 摘要
- 所有對帳證據必須可重演、可驗簽、可審計

