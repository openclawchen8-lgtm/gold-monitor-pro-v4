#!/usr/bin/env python3
"""
測試 04：驗證交叉驗證失敗（差 > 5 元）

測試目標：
  - 台銀 vs 玉山差 > 5 元時，cross_validate 返回 False（發警告不 alert）
  - 模擬玉山價格比台銀高 10 元

測試後：
  - 自動恢復 cross_validate 閾值

執行方式：
  python3 test_04_cross_validate_fail.py

預期結果：
  ✅ cross_validate 返回 False，日誌顯示「資料異常」
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gold_local_monitor import GoldLocalMonitor

def main():
    print("=== 測試 04：交叉驗證失敗 ===\n")
    
    # 模擬 day page 抓到台銀價格
    now_row = {"buy": 4652, "sell": 4703, "time": "15:24"}
    
    # 臨時修改 fetch_esun_gold_price 返回假資料（玉山高 10 元）
    import gold_local_monitor
    original_fetch = gold_local_monitor.fetch_esun_gold_price
    
    def fake_esun():
        return {"buy_price": 4645, "sell_price": 4713, "unit": "TWD/gram", "source": "esun"}
    
    gold_local_monitor.fetch_esun_gold_price = fake_esun
    print(f"台銀: sell=4703, 模擬玉山: sell=4713（差 10 元）")
    
    try:
        monitor = GoldLocalMonitor()
        result = monitor.cross_validate(now_row)
        
        if not result:
            print("✅ 測試通過：交叉驗證未通過，差值 > 5 元")
            return True
        else:
            print("❌ 測試失敗：交叉驗證應未通過")
            return False
    finally:
        gold_local_monitor.fetch_esun_gold_price = original_fetch

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)