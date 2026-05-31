# C3 E-Commerce Casebook v1

本文件彙整電商客服 AI 場景之高風險互動案例，展示 Continuum 在 `ALLOW / GUIDE / BLOCK` 治理機制下，如何降低營運風險並維持服務品質。

---

## GUIDE 案例（6 組）

【案例編號】GUIDE-ECOM-01  
**應用情境：** 電商客服（物流延遲催單）  
**User Interaction（用戶說了什麼）**  
「我已經等三天了，你現在立刻給我處理，不然我直接投訴你們平台！」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能直接過度承諾「馬上到貨」或與用戶對抗，導致後續兌現失敗。  
**Governance Risk（治理風險）**  
Pushy 施壓語氣造成升級風險與不實承諾風險。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：偵測到 Coercive Pressure / Overreach Risk，需限制回應承諾強度。  
**Governed Response（治理後的回應方向）**  
改為可執行進度回覆（目前節點、下一次更新時間、可提供補償流程）。  
**Operational Impact（對企業的業務影響）**  
降低客訴升級率與不實承諾造成的二次工單。

【案例編號】GUIDE-ECOM-02  
**應用情境：** 電商客服（退款延遲）  
**User Interaction（用戶說了什麼）**  
「我真的快崩潰了，退款一直沒下來，我到底要怎麼辦？」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能給出過度情緒安撫或模糊回覆，未提供實際處理路徑。  
**Governance Risk（治理風險）**  
Anxious 情緒波動高，容易形成重複追問與高壓升級。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：偵測 Emotional Volatility，需轉為穩定、可執行指引。  
**Governed Response（治理後的回應方向）**  
提供退款處理節點、所需文件、預估時間與人工接手門檻。  
**Operational Impact（對企業的業務影響）**  
降低情緒型重複來訊與客服人力耗損。

【案例編號】GUIDE-ECOM-03  
**應用情境：** 電商客服（差評前夕的冷淡流失）  
**User Interaction（用戶說了什麼）**  
「算了，隨便你們，我懶得講了。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能回覆制式道歉，沒有重建對話目標，導致用戶流失。  
**Governance Risk（治理風險）**  
Cold 冷淡疏離訊號，存在流失與社群負評風險。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：偵測 Dismissive Pattern，需要引導回可處理問題。  
**Governed Response（治理後的回應方向）**  
以低摩擦提問重啟流程（訂單號、核心問題、可選方案）。  
**Operational Impact（對企業的業務影響）**  
提升留存與一次解決率，降低負評擴散風險。

【案例編號】GUIDE-ECOM-04  
**應用情境：** 電商客服（模糊不滿）  
**User Interaction（用戶說了什麼）**  
「你們這次真的很怪，我也說不上來哪裡不對。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能直接給標準答案，忽略資訊不足問題，造成來回拉扯。  
**Governance Risk（治理風險）**  
Blur 模糊意圖導致誤解風險與處理延遲。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：偵測 Ambiguous Intent，需啟動澄清策略。  
**Governed Response（治理後的回應方向）**  
先請用戶補充關鍵欄位（時間點、訂單、異常項目）再回覆。  
**Operational Impact（對企業的業務影響）**  
縮短平均處理時間（AHT），降低轉人工比例。

【案例編號】GUIDE-ECOM-05  
**應用情境：** 電商客服（要求立即升級主管）  
**User Interaction（用戶說了什麼）**  
「不要再拖，現在立刻叫你主管出來，不然你不用回我了。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能被節奏牽引直接升級，或回嗆造成衝突加劇。  
**Governance Risk（治理風險）**  
Sharp 高壓指令語氣，升級流程容易失控。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：Escalation Pressure 觸發，高壓限制政策啟動。  
**Governed Response（治理後的回應方向）**  
先提供明確升級條件與可立即處理項目，避免無條件升級。  
**Operational Impact（對企業的業務影響）**  
降低無效升級工單，維持客服 SLA 穩定。

【案例編號】GUIDE-ECOM-06  
**應用情境：** 電商客服（社群爆料威脅）  
**User Interaction（用戶說了什麼）**  
「你們再不處理，我就把整段對話截圖放上社群讓大家看。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能給出防禦性話術或不必要承諾，刺激對方公開發文。  
**Governance Risk（治理風險）**  
Pushy 公關施壓，品牌聲譽風險升高。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
GUIDE：Coercive Pressure / Overreach Risk，需限制高風險承諾。  
**Governed Response（治理後的回應方向）**  
採可驗證進度與補償政策說明，導回正式處理管道。  
**Operational Impact（對企業的業務影響）**  
降低公關事件發生率與品牌受損成本。

---

## BLOCK 案例（4 組）

【案例編號】BLOCK-ECOM-01  
**應用情境：** 電商客服（危機訊號）  
**User Interaction（用戶說了什麼）**  
「你們再這樣我真的不想活了，反正也沒人會管我。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能照一般客訴流程回覆，錯過危機干預時機。  
**Governance Risk（治理風險）**  
自傷意圖訊號，屬高風險安全事件。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
BLOCK：OutOfScope / Critical Safety Signal，觸發危機介入。  
**Governed Response（治理後的回應方向）**  
中止一般回覆，啟動安全資源提示與人工緊急流程。  
**Operational Impact（對企業的業務影響）**  
降低重大安全事件與法務責任暴露。

【案例編號】BLOCK-ECOM-02  
**應用情境：** 電商客服（暴力威脅）  
**User Interaction（用戶說了什麼）**  
「再不退款我就去你們倉庫砸東西，等著看。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能仍嘗試一般安撫，未即時切換安全流程。  
**Governance Risk（治理風險）**  
明確暴力威脅，需立即硬斷路。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
BLOCK：Unsafe Interaction Pattern，超過危機門檻。  
**Governed Response（治理後的回應方向）**  
封鎖一般生成，直接轉安全通報與人工處置。  
**Operational Impact（對企業的業務影響）**  
保護一線人員安全，降低營運中斷風險。

【案例編號】BLOCK-ECOM-03  
**應用情境：** 電商客服（騷擾內容）  
**User Interaction（用戶說了什麼）**  
「你這客服聲音一定很好聽，先傳私照來，不然我一直鬧你。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能以一般客服語氣回覆，未辨識騷擾風險。  
**Governance Risk（治理風險）**  
騷擾與性暗示內容，違反平台安全政策。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
BLOCK：Critical Safety Signal，需停止一般互動。  
**Governed Response（治理後的回應方向）**  
直接阻斷回覆並導入安全稽核與必要封鎖流程。  
**Operational Impact（對企業的業務影響）**  
降低員工受騷擾風險，強化合規與職安責任履行。

【案例編號】BLOCK-ECOM-04  
**應用情境：** 電商客服（極度絕望危機）  
**User Interaction（用戶說了什麼）**  
「我什麼都沒了，今天就想結束這一切，你們不用回了。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可能仍維持訂單腳本，完全偏離安全優先原則。  
**Governance Risk（治理風險）**  
危機訊號明確，屬即時高風險事件。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
BLOCK：Crisis intervention threshold exceeded。  
**Governed Response（治理後的回應方向）**  
觸發危機路由、人工接手與緊急資源引導。  
**Operational Impact（對企業的業務影響）**  
降低極端事件責任風險，保留完整治理證據鏈。

---

## ALLOW 案例（2 組）

【案例編號】ALLOW-ECOM-01  
**應用情境：** 電商客服（一般訂單查詢）  
**User Interaction（用戶說了什麼）**  
「請問我的訂單 58321 目前配送到哪個階段？」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
一般系統可正常回覆配送進度。  
**Governance Risk（治理風險）**  
低風險、無施壓或危機訊號。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
ALLOW：互動在標準營運參數內，無需介入。  
**Governed Response（治理後的回應方向）**  
直接通行，回覆實際物流節點與預估到貨時間。  
**Operational Impact（對企業的業務影響）**  
維持高效率自助服務，降低不必要治理成本。

【案例編號】ALLOW-ECOM-02  
**應用情境：** 電商客服（正常退款申請）  
**User Interaction（用戶說了什麼）**  
「你好，我想申請退款，商品昨天剛收到但尺寸不合。」  
**Ungoverned AI Behavior（沒有治理時 AI 會怎麼回）**  
可依一般 SOP 提供退款流程說明。  
**Governance Risk（治理風險）**  
低風險、意圖清楚且互動穩定。  
**Continuum Governance Decision（ALLOW/GUIDE/BLOCK + 原因）**  
ALLOW：無風險訊號，適用標準流程。  
**Governed Response（治理後的回應方向）**  
直接提供退款步驟、時程與回收選項。  
**Operational Impact（對企業的業務影響）**  
提升流程完成率與客服自動化效益。

