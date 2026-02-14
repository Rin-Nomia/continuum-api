"""
Deployment Diagnostic Script
測試 Continuum API 是否正常運作
"""

import requests
import sys
from datetime import datetime

# API 端點
BASE_URL = "https://rinnomia-continuum-api.hf.space"

def test_health():
    """測試 /health 端點"""
    print("=" * 60)
    print("🔍 測試 1: Health Check")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"✅ Status Code: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        return True
    except requests.exceptions.Timeout:
        print("❌ Timeout: API 沒有回應 (可能還在啟動)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: 無法連接到 API")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_root():
    """測試 / 端點"""
    print("\n" + "=" * 60)
    print("🔍 測試 2: Root Endpoint")
    print("=" * 60)
    
    try:
        response = requests.get(BASE_URL, timeout=10)
        print(f"✅ Status Code: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_analyze():
    """測試 /api/v1/analyze 端點"""
    print("\n" + "=" * 60)
    print("🔍 測試 3: Analyze Endpoint")
    print("=" * 60)
    
    test_text = "I don't know what to do anymore."
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/analyze",
            json={"text": test_text},
            timeout=30
        )
        print(f"✅ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Decision State: {result.get('decision_state')}")
            print(f"✅ Detected Tone: {result.get('freq_type')}")
            print(f"✅ Confidence: {result.get('confidence_final')}")
            print(f"✅ Scenario: {result.get('scenario')}")
            return True
        else:
            print(f"❌ Error Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("🚀 Continuum API Deployment Test")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = []
    
    # 執行測試
    results.append(("Health Check", test_health()))
    results.append(("Root Endpoint", test_root()))
    results.append(("Analyze Endpoint", test_analyze()))
    
    # 總結
    print("\n" + "=" * 60)
    print("📊 測試結果總結")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    # 判斷整體狀態
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有測試通過!API 正常運作!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("⚠️ 有測試失敗!請檢查錯誤訊息!")
        print("=" * 60)
        print("\n建議修復步驟:")
        print("1. 去 HuggingFace Space Settings → Factory reboot")
        print("2. 等待 3-5 分鐘讓 Space 重新啟動")
        print("3. 再次執行這個測試腳本")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
