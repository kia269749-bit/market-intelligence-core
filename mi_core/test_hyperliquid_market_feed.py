import unittest
from unittest.mock import patch

from mi_core.brains.hyperliquid_market_feed import (
    ALLOWED_TIMEFRAMES,
    fetch_hyperliquid_ohlcv,
)


def candle(open_ms, close_ms, price):
    return {
        "t": open_ms, "T": close_ms, "o": str(price),
        "h": str(price + 2), "l": str(price - 1),
        "c": str(price + 1), "v": "12.5",
    }


class HyperliquidMarketFeedTests(unittest.TestCase):
    def test_only_four_project_timeframes_are_allowed(self):
        self.assertEqual(ALLOWED_TIMEFRAMES, ("15m", "1h", "4h", "1d"))
        with self.assertRaises(ValueError):
            fetch_hyperliquid_ohlcv("BTC", "5m", now_ms=10_000_000)

    def test_filters_forming_candles_and_builds_ohlcv_frame(self):
        now = 10_000_000_000
        duration = 900_000
        rows = [
            candle(now - (61 - i) * duration, now - (60 - i) * duration - 1, 100 + i)
            for i in range(61)
        ]
        rows.append(candle(now, now + duration - 1, 999))
        with patch(
            "mi_core.brains.hyperliquid_market_feed._post",
            return_value=rows,
        ) as post:
            frame = fetch_hyperliquid_ohlcv(
                "BTC", "15m", bars=60, now_ms=now
            )
        post.assert_called_once()
        self.assertEqual(len(frame), 60)
        self.assertEqual(float(frame["close"].iloc[-1]), 161.0)
        self.assertEqual(int(frame.index[-1]), now - duration)


if __name__ == "__main__":
    unittest.main()
