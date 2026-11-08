import json
import time
import urllib.request
import urllib.error

from mi_core.pattern_lab import closed_ohlc, evaluate_pattern_lab

BASE = "https://data-api.binance.vision/api/v3/klines"


def fetch(symbol, interval="1h", limit=1000):
    url = (
        f"{BASE}?symbol={symbol}"
        f"&interval={interval}&limit={limit}"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Pattern-Lab/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    now_ms = int(time.time() * 1000)
    print("PATTERN LAB | REAL PUBLIC OHLC")
    print("research_only=True | live_orders=False")
    print("interval=1h | costs=0.35% round-trip")
    print("No live trading or signal changes\n")

    for symbol in ("BTCUSDT", "ETHUSDT"):
        try:
            raw = fetch(symbol)
            bars = closed_ohlc(raw, now_ms)

            if len(bars) < 100:
                print(f"{symbol}: insufficient closed candles: {len(bars)}")
                continue

            report = evaluate_pattern_lab(
                bars,
                cost_pct=0.35,
                horizon=3,
                train_fraction=0.60,
                min_train_trades=8,
                breakout_window=20,
            )

            print(f"\n===== {symbol} =====")
            print(f"Closed candles: {len(bars)}")
            print(f"First candle: {bars[0]['ts']}")
            print(f"Last candle:  {bars[-1]['ts']}")
            print("Pattern | Train trades / expectancy / PF | "
                  "Test trades / expectancy / PF | selected")

            for name, result in report["results"].items():
                tr = result["train"]
                te = result["test"]
                print(
                    f"{name} | "
                    f"{tr['trades']} / {tr['expectancy_pct']:.4f}% / "
                    f"{tr['profit_factor']} | "
                    f"{te['trades']} / {te['expectancy_pct']:.4f}% / "
                    f"{te['profit_factor']} | "
                    f"{result['selected_on_train_only']}"
                )

            print("Test net returns and drawdowns:")
            for name, result in report["results"].items():
                te = result["test"]
                print(
                    f"  {name}: net={te['net_return_pct']:.4f}% "
                    f"win_rate={te['win_rate_pct']:.2f}% "
                    f"max_dd={te['max_drawdown_pct']:.4f}%"
                )

        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"{symbol}: data fetch/parse failed: {exc}")
        except Exception as exc:
            print(f"{symbol}: run failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
