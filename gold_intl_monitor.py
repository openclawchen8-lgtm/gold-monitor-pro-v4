#!/usr/bin/env python3
"""
gold_intl_monitor.py - 🌐國際金屬現貨價格監控

監控物件：
  gold_intl:     🌐國際黃金現貨
  silver_intl:   🌐國際白銀現貨
  platinum_intl: 🌐國際鉑金現貨

資料來源：Yahoo Finance（main）→ Alpha Vantage（fallback）

比對邏輯：
  1. 抓最新報價 = now
  2. 讀快取，timestamp 在「今日近 60 分鐘內」→ 用快取當 previous
  3. 快取太舊或非今日 → 不比對，設定基準，不 alert
  4. 比對，>= 閾值 → alert
  5. 寫入快取

快取保留 7 天。
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, date
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 導入適配器
sys.path.insert(0, os.path.join(os.path.expanduser("~/scripts"), "data_adapters"))
from alpha_vantage_adapter import AlphaVantageAdapter
from yahoo_finance_adapter import YahooFinanceAdapter

# ── 配置路徑 ──────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.expanduser("~/.qclaw/gold_monitor_pro_config.json")
CACHE_DIR = "/tmp"
CACHE_MAX_DAYS = 7
INTL_CACHE_TTL_MINUTES = 60  # 快取在 60 分鐘內視為有效

def _intl_cache_file(metal: str) -> str:
    return os.path.join(CACHE_DIR, f"gold_monitor_intl_{metal}.json")


# ══════════════════════════════════════════════════════════════════════════
# Dataclass
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class InternationalPrice:
    metal: str
    price: float
    fx_rate: float
    source: str
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════
# ConfigManager
# ══════════════════════════════════════════════════════════════════════════

class ConfigManager:
    DEFAULT_CONFIG = {
        "thresholds": {"gold_intl": 25, "silver_intl": 20, "platinum_intl": 15},
        "channels": {"telegram": {"enabled": True, "bot_token": "", "chat_id": ""}},
        "alpha_vantage": {"api_key": "", "enabled": True},
        "yahoo_finance": {"enabled": True, "fallback_to_alpha_vantage": True}
    }

    def __init__(self):
        self.config = self.load()

    def load(self) -> Dict:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            config = self._deep_copy(self.DEFAULT_CONFIG)
            self._deep_merge(config, loaded)
            mappings = {"gold": "gold_intl", "silver": "silver_intl", "platinum": "platinum_intl"}
            for old, new in mappings.items():
                if old in config.get("thresholds", {}) and new not in config["thresholds"]:
                    config["thresholds"][new] = config["thresholds"].pop(old)
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
    ts_str = cache.get("updated_at", cache.get("timestamp", ""))
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
        now = datetime.now()
        return ts.date() == now.date() and (now - ts).total_seconds() <= ttl_minutes * 60
    except (ValueError, TypeError):
        return False

def _cleanup_old_cache(path: str, max_days: int = CACHE_MAX_DAYS):
    """清理超過 max_days 的快取"""
    if not os.path.exists(path):
        return
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if (datetime.now() - mtime).days > max_days:
            os.remove(path)
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════════════════
# GoldIntlMonitor 主類
# ══════════════════════════════════════════════════════════════════════════

class GoldIntlMonitor:
    METAL_DISPLAY = {"gold": "黃金", "silver": "白銀", "platinum": "鉑金"}
    METALS = ["gold", "silver", "platinum"]

    def __init__(self):
        self.config = ConfigManager()
        self.alert = AlertManager(self.config)
        self.av_adapter = AlphaVantageAdapter(
            self.config.config["alpha_vantage"].get("api_key", "")
        )
        self.yf_adapter = YahooFinanceAdapter()

    # ── 資料抓取 ─────────────────────────────────────────────────────────

    def fetch_intl_price(self, metal: str) -> Optional[InternationalPrice]:
        """抓取國際現貨價格（Yahoo → AV fallback）"""
        intl_price = None
        fx_rate = None
        source = ""

        if self.config.config["yahoo_finance"].get("enabled", True):
            intl_price = self.yf_adapter.fetch_spot_price(metal)
            fx_rate = self.yf_adapter.fetch_exchange_rate("USD", "TWD")
            if intl_price:
                source = "yahoo"
                print(f"  [Yahoo Finance] {metal}: ${intl_price} USD/oz")

        if intl_price is None and self.config.config["alpha_vantage"].get("enabled", True):
            intl_price = self.av_adapter.fetch_spot_price(metal)
            fx_rate = self.av_adapter.fetch_exchange_rate()
            if intl_price:
                source = "alpha_vantage"
                print(f"  [Alpha Vantage] {metal}: ${intl_price} USD/oz (fallback)")

        if intl_price is None:
            return None

        return InternationalPrice(
            metal=metal, price=intl_price, fx_rate=fx_rate or 0.0,
            source=source, timestamp=datetime.now().isoformat()
        )

    def fetch_intl_previous_price(self, metal: str) -> Optional[float]:
        """從 Yahoo Finance 取得前一小時的收盤價（用於快取太舊時的比對）"""
        symbol_map = {"gold": "GC=F", "silver": "SI=F", "platinum": "PL=F"}
        symbol = symbol_map.get(metal)
        if not symbol:
            return None

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=1d"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
            result = data["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            # 取倒數第二筆非 None 的收盤價
            prev_closes = [c for c in closes if c is not None]
            if len(prev_closes) >= 2:
                return float(prev_closes[-2])
            return None
        except Exception as e:
            print(f"  ❌ {metal} 歷史價格取得失敗: {e}")
            return None

    # ── 變動監控 ─────────────────────────────────────────────────────────

    def check_all(self) -> List[str]:
        alerts = []
        for metal in self.METALS:
            result = self.check(metal)
            if result:
                alerts.append(result)
        return alerts

    def check(self, metal: str) -> Optional[str]:
        """檢查單一金屬國際報價變動

        邏輯：
          1. 抓最新報價 = now
          2. 快取在今日近 60 分鐘內 → 用快取當 previous，比對
          3. 快取太舊 → 從 Yahoo Finance 抓前一小時收盤價當 previous
          4. 比對，>= 閾值 → alert
          5. 寫入快取
        """
        price = self.fetch_intl_price(metal)
        if not price:
            print(f"  ❌ {metal} 國際報價取得失敗")
            return None

        display = self.METAL_DISPLAY.get(metal, metal)
        threshold = self.config.get_threshold(f"{metal}_intl")

        print(f"  🌐 國際{display}現貨：${price.price} USD/oz ({price.source})")

        # 讀快取
        cache_path = _intl_cache_file(metal)
        cache = _load_json_cache(cache_path)
        prev_price = None

        if cache and _is_cache_fresh(cache, INTL_CACHE_TTL_MINUTES):
            prev_price = cache.get("price")
            if prev_price:
                print(f"  📋 使用快取基準：${prev_price}")
        else:
            # 快取太舊 → 從網路抓前一小時收盤
            prev_price = self.fetch_intl_previous_price(metal)
            if prev_price:
                print(f"  📋 使用前一小時收盤：${prev_price}")

        # 比對
        if prev_price is not None:
            change = abs(price.price - prev_price)
            change_pct = ((price.price - prev_price) / prev_price) * 100
            direction = "📈 上漲" if price.price > prev_price else "📉 下跌"

            if change >= threshold:
                message = (
                    f"🔔 <b>Gold Monitor Pro - 🌐國際{display}現貨 價格變動</b>\n\n"
                    f"{direction} <b>${change:,.2f}</b> ({change_pct:+.2f}%)\n\n"
                    f"🌐 <b>目前價格</b>\n"
                    f"• 現貨：<b>${price.price:,.2f} USD/oz</b>\n"
                    f"• 匯率：{price.fx_rate:.2f} TWD/USD\n"
                    f"• 來源：{price.source}\n\n"
                    f"🌐 <b>上次價格 (${prev_price:,.2f})</b>\n\n"
                    f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📉 閾值設定：±${threshold}"
                )
                self.alert.send_alert(f"{metal}_intl", "價格變動", message)
                print(f"  🔔 已發送告警：變動 ${change:.2f}")
            else:
                print(f"  ✅ 變動 ${change:.2f}（未達閾值 ${threshold}）")

            self._save_cache(metal, price)
            return f"{metal}_intl: ${change:.2f}" if change >= threshold else None

        # 無法取得 previous：發 alert
        reason_parts = []
        if cache:
            cache_ts = cache.get('updated_at', cache.get('timestamp', '未知'))
            reason_parts.append(f"快取太舊（updated_at={cache_ts}，非今日近60分鐘）")
        else:
            reason_parts.append("快取不存在")
        reason_parts.append("Yahoo Finance 前一小時收盤價抓取失敗")

        message = (
            f"⚠️ <b>Gold Monitor Pro - 🌐國際{display}現貨 基準取得失敗</b>\n\n"
            f"快取及前一小時收盤都無法取得基準價格。\n\n"
            f"• 原因：{'；'.join(reason_parts)}\n"
            f"• 金屬：{display}\n\n"
            f"⏰ 時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.alert.send_alert(f"{metal}_intl", "基準取得失敗", message)
        print(f"  ⚠️ 基準取得失敗，已發 alert")
        self._save_cache(metal, price)
        return None

    # ── 快取 ─────────────────────────────────────────────────────────────

    def _save_cache(self, metal: str, price: InternationalPrice):
        cache_path = _intl_cache_file(metal)
        _cleanup_old_cache(cache_path)
        _save_json_cache(cache_path, {
            "metal": metal,
            "price": price.price,
            "fx_rate": price.fx_rate,
            "date": date.today().isoformat(),
            "timestamp": price.timestamp,
            "updated_at": datetime.now().isoformat(),
            "source": price.source
        })


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="🌐國際金屬現貨價格監控")
    parser.add_argument("--check", action="store_true", help="檢查價格變動")
    args = parser.parse_args()

    monitor = GoldIntlMonitor()

    print(f"\n{'='*50}")
    print(f"🌐 國際金屬現貨價格監控")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    if args.check:
        monitor.check_all()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
