#!/usr/bin/env python3
"""
測試 3：gold_local alert 觸發
作法：調低閾值 gold_local=1，刪快取，強制觸發 alert
"""
import sys
sys.path.insert(0, '/Users/claw/Projects/gold-monitor-pro-v4')
import gold_local_monitor as gm
import os

monitor = gm.GoldLocalMonitor()
monitor.config.config['thresholds']['gold_local'] = 1

# 刪快取
if os.path.exists(gm.LOCAL_CACHE_FILE):
    os.remove(gm.LOCAL_CACHE_FILE)

monitor.check()
