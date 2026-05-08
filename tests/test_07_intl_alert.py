#!/usr/bin/env python3
"""
測試 07：驗證 gold_intl alert 觸發

測試目標：
  - 將 gold_intl 閾值調低（25 → 0.01），強制觸發 alert

測試前：
  - 刪快取讓它用前一小時收盤比對

測試後：
  - 自動恢復閾值

執行方式：
  python3 test_07_intl_alert.py

預期結果：
  ✅ gold_intl alert 發送成功，訊息顯示「🌐國際黃金現貨」
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

CACHE_DIR = "/tmp"
CONFIG_FILE = os.path.expanduser("~/.qclaw/gold_monitor_pro_config.json")

def main():
    print("=== 測試 07：gold_intl alert 觸發 ===\n")
    
    # 刪快取
    for metal in ["gold", "silver", "platinum"]:
        cache_file = os.path.join(CACHE_DIR, f"gold_monitor_intl_{metal}.json")
        if os.path.exists(cache_file):
            os.remove(cache_file)
    print("已刪除所有 intl 快取")
    
    # 讀 config，暫時改 gold_intl 閾值
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    original = config.get("thresholds", {}).get("gold_intl", 25)
    config["thresholds"]["gold_intl"] = 0.01  # 設到最低
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"gold_intl 閾值: {original} → 0.01")
    
    try:
        from gold_intl_monitor import GoldIntlMonitor
        monitor = GoldIntlMonitor()
        result = monitor.check()
        
        if result:
            print(f"✅ 測試通過：gold_intl alert 已觸發 ({result})")
            return True
        else:
            print("❌ 測試失敗：未觸發 alert")
            return False
    finally:
        config["thresholds"]["gold_intl"] = original
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"gold_intl 閾值已恢復: {original}")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)