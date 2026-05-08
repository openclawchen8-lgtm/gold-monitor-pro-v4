#!/usr/bin/env python3
"""
測試 01：驗證 gold_local 價格與台銀官網一致

測試目標：
  - 程式抓取的台銀黃金存摺價格與官網一致（差 <= 1 元）

執行方式：
  python3 test_01_local_price_match.py

預期結果：
  ✅ 程式 sell/buy 與官網差 <= 1 元
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import urllib.request
from gold_local_monitor import GoldLocalMonitor

def fetch_official_price():
    """從台銀官網抓取最後一筆價格"""
    url = "https://rate.bot.com.tw/gold/chart/day/TWD"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8")
    
    pattern = (
        r'<td class="text-center">(\d{2}:\d{2})</td>\s*'
        r'<td class="text-center hidden-phone">[^<]*</td>\s*'
        r'<td class="text-center hidden-phone">[^<]*</td>\s*'
        r'<td class="text-right">([\d,]+)</td>\s*'
        r'<td class="text-right">([\d,]+)</td>'
    )
    matches = re.findall(pattern, html)
    if matches:
        last = matches[-1]
        return {
            "time": last[0],
            "buy": int(last[1].replace(",", "")),
            "sell": int(last[2].replace(",", ""))
        }
    return None

def main():
    print("=== 測試 01：gold_local 價格與官網一致 ===\n")
    
    # 抓官網價格
    official = fetch_official_price()
    if not official:
        print("❌ 無法從官網抓取價格")
        return False
    
    print(f"官網最後一筆: time={official['time']} buy={official['buy']} sell={official['sell']}")
    
    # 抓程式價格
    monitor = GoldLocalMonitor()
    rows = monitor.fetch_gold_local_all()
    if not rows:
        print("❌ 程式無法抓取價格")
        return False
    
    prog = rows[-1]
    print(f"程式最後一筆: time={prog['time']} buy={prog['buy']} sell={prog['sell']}")
    
    # 比對
    buy_diff = abs(official['buy'] - prog['buy'])
    sell_diff = abs(official['sell'] - prog['sell'])
    
    print(f"\n差值: buy={buy_diff} sell={sell_diff}")
    
    if buy_diff <= 1 and sell_diff <= 1:
        print("✅ 測試通過：價格一致")
        return True
    else:
        print("❌ 測試失敗：價格不一致")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
