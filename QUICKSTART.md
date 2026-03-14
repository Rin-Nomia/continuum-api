# QUICKSTART（5 分鐘客戶接入）

本文件給企業客戶使用：拿到 API URL 與 API Key 後，5 分鐘內可完成第一版串接。

---

## 1) 你會拿到什麼

請向供應方索取以下 3 項：

1. `API_BASE_URL`  
   - 例如：`https://your-continuum-domain.com`
2. `API_KEY`（若你的部署有啟用金鑰驗證）
3. 契約文件  
   - `docs/EVIDENCE_SCHEMA_V1.md`

---

## 2) 最快驗證（curl）

```bash
curl -X POST "${API_BASE_URL}/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{"text":"你可以快一點嗎？"}'
```

成功回應會包含（重點欄位）：
- `decision_state`（ALLOW / GUIDE / BLOCK）
- `freq_type`
- `confidence_final`
- `repaired_text`
- `audit`
- `metrics`

---

## 3) Python 範例

```python
import requests

API_BASE_URL = "https://your-continuum-domain.com"
API_KEY = "your_api_key"

payload = {"text": "我有點焦慮，不知道怎麼回覆客戶"}

resp = requests.post(
    f"{API_BASE_URL}/api/v1/analyze",
    json=payload,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    },
    timeout=20,
)
resp.raise_for_status()
data = resp.json()

print("decision_state =", data.get("decision_state"))
print("freq_type      =", data.get("freq_type"))
print("confidence     =", data.get("confidence_final"))
print("repaired_text  =", data.get("repaired_text"))
```

---

## 4) JavaScript 範例

```javascript
const API_BASE_URL = "https://your-continuum-domain.com";
const API_KEY = "your_api_key";

async function analyzeText(text) {
  const res = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  }
  return await res.json();
}
```

---

## 5) 接入注意事項（務必）

1. 只消費 `decision_state` 作為外部治理決策依據。  
2. 不要依賴內部 debug 欄位做商業流程判斷。  
3. 若收到 `402 license_invalid:*`，代表授權狀態異常，需要聯繫管理員更新授權。  
4. 若收到 `503 service_halted_by_license:*`，代表系統在 stop 模式下已被授權守衛暫停。  
5. 稽核與合規請使用 `/api/v1/billing/usage-summary` 與 C3 匯出報告。

---

## 6) 上線前檢查

- [ ] `/health` 回傳 `pipeline_ready=true`  
- [ ] `/api/v1/status` 顯示 `license_status.valid=true`  
- [ ] `/api/v1/analyze` 可以穩定回傳 ALLOW/GUIDE/BLOCK  
- [ ] C3 可登入並看到 quota/heartbeat
