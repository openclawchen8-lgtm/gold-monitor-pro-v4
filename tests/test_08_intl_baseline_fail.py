#!/usr/bin/env python3
"""
測試 08：驗證 gold_intl 基準取得失敗

測試目標：
  - 模擬快取太舊 + Yahoo Finance 前一小時收盤也抓不到，驗證 alert 發送

測試方式：
  - 刪快取 + Mock fetch_intl_price 和 _fetch_previous_hour 都失敗

執行方式：
  python3 test_08_intl_baseline_fail.py

預期結果：
  ✅ alert 發送成功，訊息包含「基準取得失敗」
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gold_intl_monitor
from gold_intl_monitor import GoldIntlMonitor

CACHE_DIR = "/tmp"

def main():
    print("=== 測試 08：gold_intl 基準取得失敗 ===\n")
    
    # 刪快取
    cache_file = os.path.join(CACHE_DIR, "gold_monitor_intl_gold.json")
    if os.path.exists(cache_file):
        os.remove(cache_file)
    
    # Mock fetch_intl_price 返回有效報價
    original_fetch = gold_intl_monitor.GoldIntlMonitor.fetch_intl_price
    
    def fake_fetch(self, metal):
        class FakePrice:
            metal = metal
            price = 4630.0
            fx_rate = 31.6
            source = "mock"
            timestamp = "2026-05-01T00:00:00"
        return FakePrice()
    
    # Mock _fetch_previous_hour 返回 None
    original_prev = gold_intl_monitor.GoldIntlMonitor._fetch_previous_hour
    
    def fake_prev(self, metal):
        return None
    
    gold_intl_monitor.GoldIntlMonitor.fetch_intl_price = fake_fetch
    gold_intl_monitor.GoldIntlMonitor._fetch_previous_hour = fake_prev
    
    print("Mock: fetch_intl_price 返回有效價格, _fetch_previous_hour 返回 None")
    
    try:
        monitor = GoldIntlMonitor()
        result = monitor.check()
        
        if result == "gold_intl: 基準取得失敗":
            print("✅ 測試通過：基準取得失敗，alert 已發送")
            return True
        else:
            print(f"❌ 測試失敗：result={result}")
            return False
    finally:
        gold_intl_monitor.GoldIntlMonitor.fetch_intl_price = original_fetch
        gold_intl_monitor.GoldIntlMonitor._fetch_previous_hour = original_prev

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)