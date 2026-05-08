# Gold Monitor Pro v4 測試套件

## 測試清單

| 測試 | 檔案 | 說明 |
|------|------|------|
| T01 | `test_01_local_price_match.py` | 驗證 gold_local 價格與台銀官網一致 |
| T02 | `test_02_cross_validate_pass.py` | 驗證交叉驗證正常（差 <= 5 元） |
| T03 | `test_03_local_alert.py` | 驗證 gold_local alert 觸發 |
| T04 | `test_04_cross_validate_fail.py` | 驗證交叉驗證失敗（差 > 5 元） |
| T05 | `test_05_local_baseline_fail.py` | 驗證 gold_local 基準取得失敗 |
| T06 | `test_06_intl_prices.py` | 驗證國際報價（gold/silver/platinum） |
| T07 | `test_07_intl_alert.py` | 驗證 gold_intl alert 觸發 |
| T08 | `test_08_intl_baseline_fail.py` | 驗證 gold_intl 基準取得失敗 |
| T09 | `test_09_av_fallback.py` | 驗證 Yahoo → Alpha Vantage fallback |
| T10 | `test_10_cache_cleanup.py` | 驗證快取 7 天清理 |

## 執行方式

```bash
# 執行所有測試
cd /Users/claw/Projects/gold-monitor-pro-v4/tests
for f in test_*.py; do echo "=== $f ==="; python3 "$f"; done

# 單獨執行
python3 test_01_local_price_match.py
```

## 測試前置條件

- config.json 已設定 Telegram bot_token / chat_id
- 網路可連線台銀官網、玉山銀行官網、Yahoo Finance
- Alpha Vantage API key 已設定（測試 T09）

## 注意事項

- 部分測試會暫時修改閾值或 mock 資料，測試後會自動恢復
- 測試 T04 會發送「資料異常」警告到 Telegram
- 測試 T03/T07 會發送 alert 到 Telegram
- 測試 T09 的 Alpha Vantage 免費 key 有每日 25 次限制

## 測試日期

- 首次建立：2026-05-01
- 最後更新：2026-05-01
