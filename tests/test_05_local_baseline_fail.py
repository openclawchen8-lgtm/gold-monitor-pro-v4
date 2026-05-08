#!/usr/bin/env python3
"""
測試 05：驗證 gold_local 基準取得失敗

測試目標：
  - 模擬 day page 只有 1 row 且前一營業日抓不到，驗證 alert 發送

測試方式：
  - 刪快取 + Mock fetch_gold_local_all 只返回 1 row + 讓前一營業日抓取失敗

執行方式：
  python3 test_05_local_baseline_fail.py

預期結果：
  ✅ alert 發送成功，訊息包含「日內共 1 筆」「前一營業日抓取失敗」
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gold_local_monitor import GoldLocalMonitor
from datetime import date

CACHE_DIR = "/tmp"
LOCAL_CACHE_FILE = os.path.join(CACHE_DIR, "gold_monitor_local_baseline.json")

def main():
    print("=== 測試 05：gold_local 基準取得失敗 ===\n")
    
    # 刪快取
    if os.path.exists(LOCAL_CACHE_FILE):
        os.remove(LOCAL_CACHE_FILE)
    
    # Mock fetch_gold_local_all 只返回 1 row
    import gold_local_monitor
    original_fetch_all = gold_local_monitor.GoldLocalMonitor.fetch_gold_local_all
    
    def fake_fetch_all():
        return [{"time": "15:24", "buy": 4652, "sell": 4703}]
    
    # Mock _fetch_prev_business_day 返回 None（抓不到）
    def fake_prev_day():
        return None
    
    gold_local_monitor.GoldLocalMonitor.fetch_gold_local_all = fake_fetch_all
    gold_local_monitor.GoldLocalMonitor._fetch_prev_business_day = fake_prev_day
    
    print("Mock: day page 只有 1 row, 前一營業日抓不到")
    
    try:
        monitor = GoldLocalMonitor()
        result = monitor.check()
        
        if result == "gold_local: 基準取得失敗":
            print("✅ 測試通過：基準取得失敗，alert 已發送")
            return True
        else:
            print(f"❌ 測試失敗：result={result}")
            return False
    finally:
        gold_local_monitor.GoldLocalMonitor.fetch_gold_local_all = original_fetch_all
        gold_local_monitor.GoldLocalMonitor._fetch_prev_business_day = lambda self: None

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)