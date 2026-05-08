#!/usr/bin/env python3
"""
測試 02：驗證交叉驗證正常（差 <= 5 元）

測試目標：
  - 台銀 vs 玉山價格差 <= 5 元時，cross_validate 返回 True（通過）

執行方式：
  python3 test_02_cross_validate_pass.py

預期結果：
  ✅ cross_validate 返回 True（日內報價正常）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gold_local_monitor import GoldLocalMonitor

def main():
    print("=== 測試 02：交叉驗證正常 ===\n")
    
    monitor = GoldLocalMonitor()
    rows = monitor.fetch_gold_local_all()
    
    if not rows:
        print("❌ 無法抓取台銀資料")
        return False
    
    now_row = rows[-1]
    print(f"台銀: sell={now_row['sell']} buy={now_row['buy']}")
    
    result = monitor.cross_validate(now_row)
    
    if result:
        print("✅ 測試通過：交叉驗證通過（差 <= 5 元）")
        return True
    else:
        print("❌ 測試失敗：交叉驗證未通過")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)