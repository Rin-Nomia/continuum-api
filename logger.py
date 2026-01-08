"""
Continuum Logger - Simple & Clean
只負責記錄，不做其他事
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class ContinuumLogger:
    """簡單的 Continuum 記錄器"""
    
    def __init__(self, log_dir: str = "../continuum-logs/logs"):
        """
        初始化 Logger
        
        Args:
            log_dir: logs 目錄的路徑（預設指向 continuum-logs repo）
        """
        self.log_dir = log_dir
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """確保 log 目錄存在"""
        # 建立年月目錄 (例如: 2025-01)
        year_month = datetime.utcnow().strftime("%Y-%m")
        full_path = os.path.join(self.log_dir, year_month)
        os.makedirs(full_path, exist_ok=True)
    
    def log_request(
        self,
        input_text: str,
        mode: str,
        freq_type: str,
        confidence: float,
        scenario: str,
        scenario_confidence: float,
        rhythm: Dict[str, float],
        repair_mode: str,
        repair_method: str,
        repaired_text: str,
        processing_time_ms: float,
        api_calls: int = 1,
        api_cost_usd: float = 0.0
    ) -> str:
        """
        記錄一次請求
        
        Args:
            input_text: 原始輸入文字
            mode: 使用者選擇的模式 (auto_repair, suggest, etc.)
            freq_type: 偵測到的語氣類型
            confidence: 語氣判斷的信心值
            scenario: 偵測到的場景
            scenario_confidence: 場景判斷的信心值
            rhythm: 節奏層數據 {speed_index, emotion_rate, pause_density}
            repair_mode: 修復模式 (repair, suggest, manual_review, none)
            repair_method: 修復方法 (llm, keyword, none)
            repaired_text: 修復後的文字
            processing_time_ms: 處理時間（毫秒）
            api_calls: API 呼叫次數
            api_cost_usd: API 成本
        
        Returns:
            log 的 session_id
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        session_id = self._generate_session_id()
        
        # 建立 log entry
        log_entry = {
            "timestamp": timestamp,
            "session_id": session_id,
            
            "input": {
                "text": input_text,
                "text_length": len(input_text),
                "mode": mode
            },
            
            "detection": {
                "freq_type": freq_type,
                "confidence": confidence,
                "scenario": scenario,
                "scenario_confidence": scenario_confidence,
                "rhythm": rhythm
            },
            
            "repair": {
                "mode": repair_mode,
                "method": repair_method,
                "repaired_text": repaired_text,
                "text_length": len(repaired_text),
                "length_change": len(repaired_text) - len(input_text)
            },
            
            "performance": {
                "processing_time_ms": processing_time_ms,
                "api_calls": api_calls,
                "api_cost_usd": api_cost_usd
            },
            
            "flags": self._generate_flags(
                freq_type, confidence, repair_mode, 
                input_text, repaired_text
            )
        }
        
        # 寫入 JSONL 檔案
        self._write_log(log_entry)
        
        return session_id
    
    def _generate_session_id(self) -> str:
        """產生隨機 session ID"""
        import random
        import string
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=8))
    
    def _generate_flags(
        self,
        freq_type: str,
        confidence: float,
        repair_mode: str,
        input_text: str,
        repaired_text: str
    ) -> Dict[str, bool]:
        """
        自動產生 flags
        
        這些 flags 用來快速篩選需要關注的案例
        """
        flags = {
            "unknown_type": freq_type == "Unknown",
            "low_confidence": confidence < 0.4,
            "manual_review_needed": repair_mode == "manual_review",
            "repair_quality_concern": False
        }
        
        # 偵測修復品質問題
        if repair_mode == "repair":
            concerns = self._detect_repair_concerns(input_text, repaired_text, confidence)
            flags["repair_quality_concern"] = len(concerns) > 0
        
        return flags
    
    def _detect_repair_concerns(
        self,
        input_text: str,
        repaired_text: str,
        confidence: float
    ) -> list:
        """
        偵測修復品質問題
        
        Returns:
            問題清單（空清單 = 沒問題）
        """
        concerns = []
        
        input_len = len(input_text)
        repaired_len = len(repaired_text)
        
        # Rule 1: 改太多（長度變化超過 50%）
        if input_len > 0:
            length_change_pct = abs(repaired_len - input_len) / input_len
            if length_change_pct > 0.5:
                concerns.append("length_change_too_large")
        
        # Rule 2: 改太長（超過 200 字）
        if repaired_len > 200:
            concerns.append("repaired_text_too_long")
        
        # Rule 3: 信心值低但還是修復了
        if confidence < 0.5:
            concerns.append("low_confidence_repair")
        
        # Rule 4: 檢查是否加入了不該有的敏感詞
        warning_words = ["career", "relationship", "family", "health", "money"]
        input_words = set(input_text.lower().split())
        repaired_words = set(repaired_text.lower().split())
        added_words = repaired_words - input_words
        
        if any(word in added_words for word in warning_words):
            concerns.append("added_sensitive_context")
        
        return concerns
    
    def _write_log(self, log_entry: Dict[str, Any]):
        """寫入 log 到 JSONL 檔案"""
        # 決定檔名（每天一個檔案）
        date_str = datetime.utcnow().strftime("%Y%m%d")
        year_month = datetime.utcnow().strftime("%Y-%m")
        
        log_file = os.path.join(
            self.log_dir,
            year_month,
            f"{date_str}.jsonl"
        )
        
        # 寫入（append mode）
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


# 簡單的使用範例
if __name__ == "__main__":
    # 初始化 logger
    logger = ContinuumLogger()
    
    # 記錄一次請求
    session_id = logger.log_request(
        input_text="Just do what I said, it's not that hard",
        mode="auto_repair",
        freq_type="Sharp",
        confidence=0.85,
        scenario="internal_communication",
        scenario_confidence=0.72,
        rhythm={
            "speed_index": 0.78,
            "emotion_rate": 0.65,
            "pause_density": 0.12
        },
        repair_mode="repair",
        repair_method="llm",
        repaired_text="Could you help with this? I think it would work well",
        processing_time_ms=1234.5,
        api_calls=1,
        api_cost_usd=0.0012
    )
    
    print(f"✅ Logged with session_id: {session_id}")
```

---

# 關於「怎麼看」自動備份和報告

---

## **自動備份（GitHub Actions）**

### **它會做什麼：**

每天固定時間（例如：UTC 00:00，台灣早上 8:00）：
```
1. 檢查 continuum-logs/logs/ 裡面有沒有新的 log 檔案
2. 如果有 → git add + git commit + git push
3. 如果沒有 → 什麼都不做
```

### **你怎麼看到結果：**

**方式 1：GitHub 網頁上看**
```
1. 打開 https://github.com/rin-nomia/continuum-logs
2. 看 commits 記錄
3. 會看到：
   - "Auto backup 2025-01-06" (by GitHub Actions)
   - "Auto backup 2025-01-07" (by GitHub Actions)
