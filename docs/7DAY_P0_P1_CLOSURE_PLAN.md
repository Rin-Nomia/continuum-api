# Continuum 7 天補齊清單（P0 → P1）

## Day 1（P0）— 契約一致性封口

- [x] Public response 強制 `decision_state`（ALLOW/GUIDE/BLOCK）
- [x] API 輸入長度與 pipeline 門檻對齊（min/max）
- [x] mode/decision_state 不一致時以 app truth 修正並記錄 warning
- 驗收：
  - `/api/v1/analyze` 不再輸出 raw input 欄位
  - `metrics.decision_state` 始終在三態值域內

## Day 2（P0）— LLM 路徑可靠性

- [x] 修正 `repairer` 與 `RobustAPIClient` 介面不一致
- [x] 補 `complete()/generate()` compatibility shim
- 驗收：
  - repairer 可穩定調用 client，不因方法不存在直接失效

## Day 3（P0）— 可重現與部署邊界

- [ ] 建立 `continuum-api` 對 `z1_mvp` 的可重現依賴方案（子模組或打包釋出）
- [ ] 在 CI 做「獨立 checkout 可啟動」驗證
- 驗收：
  - 不依賴本機工作區特殊結構即可啟動

## Day 4（P1）— 運維可視化

- [x] 新增 `/api/v1/ops/metrics`
  - decision_state 分布
  - p50/p95/p99 latency
  - llm usage rate
  - oos hit rate
- [x] status dashboard 串接 runtime status
- 驗收：
  - 儀表板與 ops endpoint 數據一致

## Day 5（P1）— 可簽約文件

- [x] CHANGELOG.md
- [x] VERSIONING_POLICY.md
- [x] SLA.md（草案）
- 驗收：
  - release 變更可追溯
  - 合約前置文件齊備

## Day 6（P1）— 模板與規則覆蓋

- [x] `templates.json` 補齊 `Rhythm` 在 repair/suggest
- [ ] 模板內容做 assistant voice / question mark / markdown 風險掃描與修補
- 驗收：
  - 七類 tone（含 Rhythm, Unknown）模板覆蓋完整

## Day 7（P1）— 商業級測試關卡

- [ ] 建立 30×4（ALLOW/GUIDE/REPAIR/BLOCK）測試集
- [ ] 每句重跑 10 次，驗證決策穩定
- [ ] OOS 誤殺率報告
- 驗收：
  - 可輸出「可預期性」測試報告給客戶/法務

---

## 目前進度摘要

- 已完成：Day 1、Day 2、Day 4、Day 5、Day 6（部分）
- 待完成：Day 3（可重現依賴方案）、Day 7（商業級測試集與報告）

