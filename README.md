# Z1 Tone Firewall API

自動從 z1_mvp 同步並部署

## 🏗️ 架構
```
z1-api (本 repo)
  ├── app.py              ← 你建立的
  ├── requirements.txt    ← 你建立的
  └── .github/workflows/  ← 你建立的

自動同步 (GitHub Actions)：
  ├── pipeline/           ← 從 z1_mvp 複製
  ├── core/               ← 從 z1_mvp 複製
  └── configs/            ← 從 z1_mvp 複製
```

## 📊 系統狀態

- **準確率：** 95%（基於 Rin 對齊度測試）
- **支援語氣：** Anxious, Cold, Sharp, Blur, Pushy
- **修復引擎：** Claude Haiku (LLM) + 關鍵字替換 (Fallback)
- **場景偵測：** 4 種場景（客服、社交、內部溝通、商業）

## 🚀 API 端點

### 健康檢查
```bash
GET https://Rin-Nomia-z1-tone-api.hf.space/health
```

### 單句分析
```bash
POST https://Rin-Nomia-z1-tone-api.hf.space/api/v1/analyze

{
  "text": "你的文字"
}
```

**回傳範例：**
```json
{
  "original": "你的文字",
  "freq_type": "Sharp",
  "confidence": 0.85,
  "scenario": "internal_communication",
  "repaired_text": "修復後的文字"
}
```

## 📖 API 文件

部署後訪問：
- Swagger UI: `https://Rin-Nomia-z1-tone-api.hf.space/docs`
- ReDoc: `https://Rin-Nomia-z1-tone-api.hf.space/redoc`

## ⚙️ 設定步驟

### 1. 建立 HuggingFace Space

1. 去 https://huggingface.co/spaces
2. 點 "Create new Space"
3. 名稱：`z1-tone-api`
4. SDK：選 `Docker`
5. Visibility: Public
6. Create

### 2. 確認 Secrets

在本 repo 的 **Settings → Secrets → Actions** 確認有這些：

- ✅ `GH_PAT`：GitHub Token（已有）
- ✅ `HF_TOKEN`：HuggingFace Token（已有）
- ✅ `ANTHROPIC_API_KEY`：Claude API Key（已有）

### 3. 觸發部署

1. 進入 **Actions** 頁籤
2. 選擇 "同步 z1_mvp 並部署 API"
3. 點 **Run workflow**
4. 等待 5-10 分鐘

## 🔄 自動同步機制

- **觸發條件：** 每次 push 到 main branch
- **同步內容：** 自動從 `Rin-Nomia/z1_mvp` 複製最新的 pipeline, core, configs
- **優點：** z1_mvp 更新後，API 也自動更新

## 🧪 測試
```bash
# 測試健康檢查
curl https://Rin-Nomia-z1-tone-api.hf.space/health

# 測試分析
curl -X POST https://Rin-Nomia-z1-tone-api.hf.space/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "測試文字"}'
```

## ⚠️ 注意事項

- **不要手動編輯** pipeline, core, configs（會被覆蓋）
- 要改功能請去 **z1_mvp** 改，然後會自動同步過來
- API 使用 z1_mvp 的完整 Pipeline，包含 LLM 修復

## 📊 效能指標

- 單次分析：~1-2 秒
- 信心值門檻：0.2（使用 LLM）
- 速率限制：50 req/min
- 快取：24 小時 TTL

## 🔗 相關連結

- z1_mvp repo: https://github.com/Rin-Nomia/z1_mvp
- HuggingFace Space: https://huggingface.co/spaces/Rin-Nomia/z1-tone-api
- API Docs: https://Rin-Nomia-z1-tone-api.hf.space/docs

---

Built with ❤️ by Rin | Powered by Claude 4
```

---

## 🎯 操作步驟（完整版）

### Step 1：建立新 Repo
```
1. 去 https://github.com/Rin-Nomia
2. 點右上角 "+" → "New repository"
3. Repository name: z1-api
4. Description: Z1 Tone Firewall API
5. Public
6. 不要勾選 "Add a README file"
7. Create repository
```

---

### Step 2：建立檔案 1 - app.py
```
1. 在新建立的 z1-api repo 頁面
2. 點 "creating a new file"
3. 檔案名稱輸入：app.py
4. 複製上面「檔案 1」的完整內容
5. 貼到編輯器
6. 下方 Commit 訊息：Create app.py
7. 點 "Commit new file"
```

---

### Step 3：建立檔案 2 - requirements.txt
```
1. 回到 z1-api repo 首頁
2. 點 "Add file" → "Create new file"
3. 檔案名稱：requirements.txt
4. 複製上面「檔案 2」的完整內容
5. 貼上
6. Commit new file
```

---

### Step 4：建立檔案 3 - workflow
```
1. 回到 z1-api repo 首頁
2. 點 "Add file" → "Create new file"
3. 檔案名稱：.github/workflows/sync_and_deploy.yml
   ⚠️ 注意：要完整輸入路徑，包含 .github/workflows/
4. 複製上面「檔案 3」的完整內容（已改好你的用戶名）
5. 貼上
6. Commit new file
```

---

### Step 5：建立檔案 4 - README
```
1. 回到 z1-api repo 首頁
2. 點 "Add file" → "Create new file"
3. 檔案名稱：README.md
4. 複製上面「檔案 4」的完整內容（已改好你的用戶名）
5. 貼上
6. Commit new file
```

---

### Step 6：建立 HuggingFace Space
```
1. 去 https://huggingface.co/spaces
2. 點右上角 "Create new Space"
3. 填寫：
   - Owner: Rin-Nomia
   - Space name: z1-tone-api
   - License: Apache 2.0（或任何）
   - Select the Space SDK: Docker
   - Visibility: Public
4. 點 "Create Space"
```

---

### Step 7：觸發部署
```
1. 回到 GitHub z1-api repo
2. 點上方 "Actions" 頁籤
3. 左側會看到 "同步 z1_mvp 並部署 API"
4. 點進去
5. 右側點 "Run workflow"
6. 選 "Branch: main"
7. 點綠色 "Run workflow" 按鈕
8. 等待執行（5-10 分鐘）
```

---

### Step 8：查看結果
```
執行完成後：

1. 如果成功：
   ✅ 綠色勾勾
   ✅ 訪問 https://Rin-Nomia-z1-tone-api.hf.space/docs
   ✅ 看到 API 文件

2. 如果失敗：
   ❌ 紅色叉叉
   → 點進去看哪一關失敗
   → 告訴我錯誤訊息
```

---

## ✅ 檢查清單

在開始前確認：
```
□ GitHub 帳號：Rin-Nomia ✅
□ HuggingFace 帳號：Rin-Nomia ✅（假設跟 GitHub 一樣）
□ z1_mvp repo 存在 ✅
□ GitHub Secrets 已設定：
  □ GH_PAT
  □ HF_TOKEN
  □ ANTHROPIC_API_KEY
