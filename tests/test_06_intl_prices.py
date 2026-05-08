#!/usr/bin/env python3
"""
測試 06：驗證國際報價（gold/silver/platinum）

測試目標：
  - gold_intl, silver_intl, platinum_intl 皆可從 Yahoo Finance 取得報價

執行方式：
  python3 test_06_intl_prices.py

預期結果：
  ✅ 三個金屬皆返回有效價格（float）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gold_intl_monitor import GoldIntlMonitor

def main():
    print("=== 測試 06：國際報價 ===\n")
    
    monitor = GoldIntlMonitor()
    results = {}
    
    for metal in ["gold", "silver", "platinum"]:
        price = monitor.fetch_intl_price(metal)
        if price:
            results[metal] = price.price
            print(f"  {metal}: ${price.price} USD/oz ({price.source})")
        else:
            results[metal] = None
            print(f"  {metal}: ❌ 無法取得")
    
    if all(v is not None for v in results.values()):
        print("\n✅ 測試通過：三個金屬皆取得報價")
        return True
    else:
        failed = [k for k, v in results.items() if v is None]
        print(f"\n❌ 測試失敗：{failed} 無法取得報價")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)