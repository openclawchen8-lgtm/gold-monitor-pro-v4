#!/usr/bin/env python3
"""
測試 4：交叉驗證失敗（台銀 vs 玉山 差 > 5 元）
作法：mock fetch_esun_gold_price 回傳 sell+10 元
"""
import sys
sys.path.insert(0, '/Users/claw/Projects/gold-monitor-pro-v4')
import gold_local_monitor as gm
import os

# Mock 玉山回傳差很大的值
original = gm.fetch_esun_gold_price
def mock_esun():
    result = original()
    if result:
        result['sell_price'] = result['sell_price'] + 10  # 故意差 10 元
    return result
gm.fetch_esun_gold_price = mock_esun

monitor = gm.GoldLocalMonitor()
monitor.CROSS_VALIDATE_THRESHOLD = 5
monitor.config.config['thresholds']['gold_local'] = 1

# 刪快取
if os.path.exists(gm.LOCAL_CACHE_FILE):
    os.remove(gm.LOCAL_CACHE_FILE)

monitor.check()
