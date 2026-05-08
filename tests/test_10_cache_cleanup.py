#!/usr/bin/env python3
"""
測試 10：驗證快取 7 天清理

測試目標：
  - 超過 7 天的快取檔案會被自動刪除

測試方式：
  - 建立一個 8 天前修改時間的快取檔，執行後驗證是否刪除

執行方式：
  python3 test_10_cache_cleanup.py

預期結果：
  ✅ 8 天前的快取被刪除（`_cleanup_old_cache` 返回 True）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from datetime import datetime, timedelta

CACHE_DIR = "/tmp"
TEST_CACHE = os.path.join(CACHE_DIR, "gold_monitor_intl_gold.json")

def main():
    print("=== 測試 10：快取 7 天清理 ===\n")
    
    # 建立測試快取（8 天前）
    cache_data = {
        "metal": "gold",
        "price": 4600.0,
        "fx_rate": 31.5,
        "date": "2026-04-23",
        "timestamp": "2026-04-23T15:00:00",
        "source": "test"
    }
    with open(TEST_CACHE, "w") as f:
        json.dump(cache_data, f)
    
    # 設定 mtime 為 8 天前
    old_mtime = time.time() - (8 * 86400)
    os.utime(TEST_CACHE, (old_mtime, old_mtime))
    
    # 驗證 mtime
    mtime = os.path.getmtime(TEST_CACHE)
    days_ago = (time.time() - mtime) / 86400
    print(f"快取 mtime: {datetime.fromtimestamp(mtime)}, {days_ago:.1f} 天前")
    
    # 執行 _cleanup_old_cache
    from gold_intl_monitor import _cleanup_old_cache
    deleted = _cleanup_old_cache(CACHE_DIR, max_days=7)
    
    # 驗證
    exists = os.path.exists(TEST_CACHE)
    print(f"清理後是否存在: {exists}")
    
    if not exists:
        print("✅ 測試通過：8 天前的快取已刪除")
        return True
    else:
        print("❌ 測試失敗：快取未被刪除")
        # 清理測試檔
        os.remove(TEST_CACHE)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)