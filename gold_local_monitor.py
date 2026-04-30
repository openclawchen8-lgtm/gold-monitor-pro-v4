#!/usr/bin/env python3
"""
gold_local_monitor.py - 📊台銀黃金存摺價格監控

監控物件：gold_local（台銀黃金存摺）
資料來源：台銀 day page（main）+ 玉山銀行（交叉驗證）

比對邏輯：
  1. 抓 day page 最後一筆 = now
  2. 讀快取，timestamp 在「今日近 10 分鐘內」→ 用快取當 previous
  3. 快取太舊 → 重新抓 previous：
     - day page >= 2 rows → 倒數第二筆
     - day page 只有 1 row → 抓前一營業日 day page 最後一筆
  4. 比對，>= 閾值 → 交叉驗證 → alert
  5. 寫入快取

快取保留 7 天。
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 導入台銀 adapter（Playwright fallback）
sys.path.insert(0, os.path.join(os.path.expanduser("~/scripts"), "data_adapters"))
from bot_adapter import BOTAdapter

# ── 配置路徑 ──────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.expanduser("~/.qclaw/gold_monitor_pro_config.json")
CACHE_DIR = "/tmp"
LOCAL_CACHE_FILE = os.path.join(CACHE_DIR, "gold_monitor_local_baseline.json")

BOT_BASE_URL = "https://rate.bot.com.tw/gold/chart"
CACHE_MAX_DAYS = 7
LOCAL_CACHE_TTL_MINUTES = 10  # 快取在 10 分鐘內視為有效


# ══════════════════════════════════════════════════════════════════════════
# Dataclass
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class LocalGoldPrice:
    """台銀黃金存摺"""
    buy: int
    sell: int
    time: str
    date: str
    source: str
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════
# ConfigManager
# ══════════════════════════════════════════════════════════════════════════

class ConfigManager:
    DEFAULT_CONFIG = {
        "thresholds": {"gold_local": 30},
        "channels": {"telegram": {"enabled": True, "bot_token": "", "chat_id": ""}}
    }

    def __init__(self):
        self.config = self.load()

    def load(self) -> Dict:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            config = self._deep_copy(self.DEFAULT_CONFIG)
            self._deep_merge(config, loaded)
            if "gold" in config.get("thresholds", {}) and "gold_local" not in config["thresholds"]:
                config["thresholds"]["gold_local"] = config["thresholds"].pop("gold")
            return config
        return self._deep_copy(self.DEFAULT_CONFIG)

    def _deep_copy(self, obj):
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        return obj

    def _deep_merge(self, base: Dict, override: Dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get_threshold(self, monitor_id: str) -> float:
        return self.config["thresholds"].get(monitor_id, 30)

    def is_channel_enabled(self, channel: str) -> bool:
        return self.config["channels"].get(channel, {}).get("enabled", False)


# ══════════════════════════════════════════════════════════════════════════
# AlertManager
# ══════════════════════════════════════════════════════════════════════════

class AlertManager:
    def __init__(self, config: ConfigManager):
        self.config = config

    def send_telegram(self, message: str) -> bool:
        if not self.config.is_channel_enabled("telegram"):
            return False
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not bot_token or not chat_id:
            tg = self.config.config["channels"]["telegram"]
            bot_token = bot_token or tg.get("bot_token", "")
            chat_id = chat_id or tg.get("chat_id", "")
        if not bot_token or not chat_id:
            print("❌ Telegram 配置不完整", file=sys.stderr)
            return False
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id, "text": message, "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req)
            return True
        except Exception as e:
            print(f"❌ Telegram 發送失敗: {e}", file=sys.stderr)
            return False

    def send_alert(self, monitor_id: str, alert_type: str, message: str):
        if self.config.is_channel_enabled("telegram"):
            self.send_telegram(message)


# ══════════════════════════════════════════════════════════════════════════
# 快取工具
# ══════════════════════════════════════════════════════════════════════════

def _load_json_cache(path: str) -> Optional[Dict]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None

def _save_json_cache(path: str, data: Dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _is_cache_fresh(cache: Dict, ttl_minutes: int) -> bool:
    """快取的 timestamp 是否在今日近 ttl_minutes 分鐘內"""
    ts_str = cache.get("updated_at", "")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
        now = datetime.now()
        # 必須同日且在 ttl 分鐘內
        return ts.date() == now.date() and (now - ts).total_seconds() <= ttl_minutes * 60
    except (ValueError, TypeError):
        return False

def _cleanup_old_cache(path: str, max_days: int = CACHE_MAX_DAYS):
    """清理超過 max_days 的快取（檔案層級）"""
    if not os.path.exists(path):
        return
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if (datetime.now() - mtime).days > max_days:
            os.remove(path)
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════════════════
# 玉山銀行黃金存摺（直接內嵌）
# ══════════════════════════════════════════════════════════════════════════

def fetch_esun_gold_price() -> Optional[Dict]:
    url = "https://wealth.esunbank.com/zh-tw/gold/price/current-price"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ❌ 玉山銀行抓取失敗: {e}")
        return None
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    for table in tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if len(clean) >= 3 and '公克' in clean[0]:
                try:
                    return {
                        "buy_price": int(clean[1].replace(",", "")),
                        "sell_price": int(clean[2].replace(",", "")),
                        "source": "esun"
                    }
                except (ValueError, IndexError):
                    continue
    return None


# ══════════════════════════════════════════════════════════════════════════
# GoldLocalMonitor 主類
# ══════════════════════════════════════════════════════════════════════════

class GoldLocalMonitor:
    CROSS_VALIDATE_THRESHOLD = 5

    def __init__(self):
        self.config = ConfigManager()
        self.alert = AlertManager(self.config)
        self.bot_adapter = BOTAdapter()

    # ── 資料抓取 ─────────────────────────────────────────────────────────

    def fetch_day_page_rows(self, target_date: str = "") -> List[Dict]:
        """從台銀 day page 取得所有 intraday rows

        Args:
            target_date: 空字串=最新營業日，"2026-04-30"=指定日期
        """
        if target_date:
            url = f"{BOT_BASE_URL}/{target_date}/TWD"
        else:
            url = f"{BOT_BASE_URL}/day/TWD"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode("utf-8")
        except Exception as e:
            print(f"  ❌ 台銀 day page 抓取失敗 ({target_date or 'latest'}): {e}", file=sys.stderr)
            return []

        pattern = (
            r'<td class="text-center">(\d{2}:\d{2})</td>\s*'
            r'<td class="text-center hidden-phone">[^<]*</td>\s*'
            r'<td class="text-center hidden-phone">[^<]*</td>\s*'
            r'<td class="text-right">([\d,]+)</td>\s*'
            r'<td class="text-right">([\d,]+)</td>'
        )
        matches = re.findall(pattern, html)
        return [
            {"time": t, "buy": int(b.replace(",", "")), "sell": int(s.replace(",", ""))}
            for t, b, s in matches
        ]

    def fetch_prev_business_day_close(self) -> Optional[Dict]:
        """抓取前一營業日的最後一筆收盤價

        從今天往前推，最多試 5 天（處理連假）
        """
        check_date = date.today() - timedelta(days=1)
        for _ in range(5):
            date_str = check_date.isoformat()
            rows = self.fetch_day_page_rows(date_str)
            if rows:
                print(f"  📅 前一營業日 ({date_str})：最後一筆 sell={rows[-1]['sell']} ({rows[-1]['time']})")
                return rows[-1]
            check_date -= timedelta(days=1)
        print("  ❌ 找不到前一營業日資料（已往前找 5 天）")
        return None

    # ── 交叉驗證 ─────────────────────────────────────────────────────────

    def cross_validate(self, bot_price: Dict) -> bool:
        esun_result = fetch_esun_gold_price()
        if not esun_result:
            print("  ⚠️ 玉山銀行資料取得失敗，跳過交叉驗證")
            return True
        esun_sell = esun_result["sell_price"]
        bot_sell = bot_price["sell"]
        diff = abs(bot_sell - esun_sell)
        print(f"  🔍 交叉驗證：台銀 sell={bot_sell} vs 玉山 sell={esun_sell}（差 {diff} 元）")
        if diff > self.CROSS_VALIDATE_THRESHOLD:
            message = (
                f"⚠️ <b>Gold Monitor Pro - 資料異常</b>\n\n"
                f"📊 台銀黃金存摺資料可疑\n\n"
                f"• 台銀：sell={bot_sell:,}（{bot_price.get('time', 'N/A')}）\n"
                f"• 玉山：sell={esun_sell:,}\n"
                f"• 差值：{diff} 元\n\n"
                f"已暫停本次 alert，請確認官網報價。\n\n"
                f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.alert.send_alert("gold_local", "資料異常", message)
            print(f"  ⚠️ 資料異常！差值 {diff} > {self.CROSS_VALIDATE_THRESHOLD} 元，不 alert")
            return False
        return True

    # ── 變動監控 ─────────────────────────────────────────────────────────

    def check(self) -> Optional[str]:
        """檢查黃金存摺價格變動

        邏輯：
          1. 抓 day page 最後一筆 = now
          2. 快取在今日近 10 分鐘內 → 用快取當 previous
          3. 快取太舊 → 重新抓 previous：
             - day page >= 2 rows → 倒數第二筆
             - day page 只有 1 row → 前一營業日最後一筆
          4. 比對，>= 閾值 → 交叉驗證 → alert
          5. 寫入快取
        """
        rows = self.fetch_day_page_rows()
        if not rows:
            print("  ❌ 台銀黃金存摺資料取得失敗")
            return None

        threshold = self.config.get_threshold("gold_local")
        now_row = rows[-1]
        print(f"  📊 台銀黃金存摺：sell={now_row['sell']} buy={now_row['buy']} ({now_row['time']})")
        print(f"     日內共 {len(rows)} 筆報價")

        # 決定 previous
        prev_row = None
        cache = _load_json_cache(LOCAL_CACHE_FILE)

        if cache and _is_cache_fresh(cache, LOCAL_CACHE_TTL_MINUTES):
            # 快取新鮮 → 用快取
            prev_row = cache.get("now")
            if prev_row:
                print(f"  📋 使用快取基準：sell={prev_row['sell']} ({prev_row.get('time', 'N/A')})")
        else:
            # 快取太舊或無快取 → 重新抓 previous
            if len(rows) >= 2:
                prev_row = rows[-2]
                print(f"  📋 使用日內前一筆：sell={prev_row['sell']} ({prev_row['time']})")
            else:
                # 只有 1 row → 抓前一營業日
                prev_row = self.fetch_prev_business_day_close()

        if prev_row is None:
            message = (
                f"⚠️ <b>Gold Monitor Pro - 📊台銀黃金存摺 基準取得失敗</b>\n\n"
                f"快取及前一營業日都無法取得基準價格。\n\n"
                f"• 快取狀態：{'太舊（非今日近10分鐘）' if cache else '不存在'}\n"
                f"• day page rows：{len(rows)} 筆（需 >= 2 才能取前一筆）\n"
                f"• 前一營業日：抓取失敗\n\n"
                f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.alert.send_alert("gold_local", "基準取得失敗", message)
            print(f"  ⚠️ 基準取得失敗，已發 alert")
            self._save_cache(now_row)
            return None

        # 比對
        change = abs(now_row["sell"] - prev_row["sell"])
        change_pct = ((now_row["sell"] - prev_row["sell"]) / prev_row["sell"]) * 100
        direction = "📈 上漲" if now_row["sell"] > prev_row["sell"] else "📉 下跌"

        if change >= threshold:
            if not self.cross_validate(now_row):
                self._save_cache(now_row)
                return None

            message = (
                f"🔔 <b>Gold Monitor Pro - 📊台銀黃金存摺 價格變動</b>\n\n"
                f"{direction} <b>{change:,.0f} 元</b> ({change_pct:+.2f}%)\n\n"
                f"📊 <b>目前價格</b>\n"
                f"• 賣出：<b>{now_row['sell']:,} 元/公克</b>\n"
                f"• 買入：<b>{now_row['buy']:,} 元/公克</b>\n"
                f"• 時間：{now_row['time']}\n\n"
                f"📊 <b>基準價格</b>\n"
                f"• 賣出：{prev_row['sell']:,} 元/公克\n"
                f"• 買入：{prev_row['buy']:,} 元/公克\n"
                f"• 時間：{prev_row.get('time', 'N/A')}\n\n"
                f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📉 閾值設定：±{threshold} 元"
            )
            self.alert.send_alert("gold_local", "價格變動", message)
            print(f"  🔔 已發送告警：變動 {change} 元")
        else:
            print(f"  ✅ 變動 {change} 元（未達閾值 {threshold}）")

        self._save_cache(now_row)
        return f"gold_local: {change}元" if change >= threshold else None

    # ── 快取 ─────────────────────────────────────────────────────────────

    def _save_cache(self, now_row: Dict):
        _cleanup_old_cache(LOCAL_CACHE_FILE)
        _save_json_cache(LOCAL_CACHE_FILE, {
            "date": date.today().isoformat(),
            "now": now_row,
            "updated_at": datetime.now().isoformat()
        })


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="📊台銀黃金存摺價格監控")
    parser.add_argument("--check", action="store_true", help="檢查價格變動")
    args = parser.parse_args()

    monitor = GoldLocalMonitor()

    print(f"\n{'='*50}")
    print(f"📊 台銀黃金存摺價格監控")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    if args.check:
        monitor.check()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
