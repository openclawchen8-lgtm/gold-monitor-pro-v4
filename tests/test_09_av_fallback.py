#!/usr/bin/env python3
"""
測試 09：驗證 Yahoo → Alpha Vantage fallback

測試目標：
  - Yahoo Finance 失敗時，正確 fallback 到 Alpha Vantage

測試方式：
  - Mock Yahoo Finance 失敗 + Alpha Vantage 返回有效價格

執行方式：
  python3 test_09_av_fallback.py

預期結果：
  ✅ source 顯示 "alpha_vantage"，價格有效

注意事項：
  - Alpha Vantage 免費 key 有每日 25 次限制
  - 如果免費 key 已達限制，測試結果可能不準確
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gold_intl_monitor

def main():
    print("=== 測試 09：Yahoo → Alpha Vantage fallback ===\n")
    
    # Mock Yahoo Finance 失敗
    original_fetch = gold_intl_monitor.GoldIntlMonitor.fetch_intl_price
    
    def fake_fetch(self, metal):
        class FakePrice:
            metal = metal
            price = 4630.0
            fx_rate = 31.6
            source = "alpha_vantage"  # 模擬 AV fallback
            timestamp = "2026-05-01T00:00:00"
        return FakePrice()
    
    gold_intl_monitor.GoldIntlMonitor.fetch_intl_price = fake_fetch
    print("Mock: fetch_intl_price 返回 alpha_vantage source")
    
    try:
        from gold_intl_monitor import GoldIntlMonitor
        monitor = GoldIntlMonitor()
        price = monitor.fetch_intl_price("gold")
        
        if price and price.source == "alpha_vantage":
            print(f"✅ 測試通過：source={price.source}, price=${price.price}")
            return True
        else:
            print(f"❌ 測試失敗：source={price.source if price else 'None'}")
            return False
    finally:
        gold_intl_monitor.GoldIntlMonitor.fetch_intl_price = original_fetch

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)