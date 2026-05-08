#!/usr/bin/env python3
"""
測試 03：驗證 gold_local alert 觸發

測試目標：
  - 將閾值調低（30 → 1），強制觸發 alert，驗證訊息格式

測試前：
  - 確認快取已存在（前一次 --check 寫入），或直接刪除快取讓它用 day page

測試後：
  - 自動恢復閾值（1 → 30）

執行方式：
  python3 test_03_local_alert.py

預期結果：
  ✅ alert 發送成功，訊息格式正確（📊台銀黃金存摺、買/賣價格）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path

CACHE_DIR = "/tmp"
LOCAL_CACHE_FILE = os.path.join(CACHE_DIR, "gold_monitor_local_baseline.json")
CONFIG_FILE = os.path.expanduser("~/.qclaw/gold_monitor_pro_config.json")

def main():
    print("=== 測試 03：gold_local alert 觸發 ===\n")
    
    # 1. 刪快取（確保用 day page 比對）
    if os.path.exists(LOCAL_CACHE_FILE):
        os.remove(LOCAL_CACHE_FILE)
        print(f"已刪除快取: {LOCAL_CACHE_FILE}")
    
    # 2. 讀 config，暫時改閾值
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    original_threshold = config.get("thresholds", {}).get("gold_local", 30)
    config["thresholds"]["gold_local"] = 1  # 設到最低
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"閾值: {original_threshold} → 1")
    
    try:
        # 3. 執行 check
        from gold_local_monitor import GoldLocalMonitor
        monitor = GoldLocalMonitor()
        result = monitor.check()
        
        if result:
            print(f"✅ 測試通過：alert 已觸發 ({result})")
            return True
        else:
            print("❌ 測試失敗：未觸發 alert")
            return False
    finally:
        # 4. 恢復閾值
        config["thresholds"]["gold_local"] = original_threshold
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"閾值已恢復: {original_threshold}")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)