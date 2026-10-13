import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from mi_core.real_data import rows_to_bars, download

class RealDataTests(unittest.TestCase):
    def test_kline_mapping_uses_close_and_taker_buy_volume(self):
        rows = [[1700000000000, "1", "2", "0.5", "1.5", "100", 0, "0", 10, "60", "0", "0"]]
        bars = rows_to_bars(rows, "BTCUSDT")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].price, 1.5)
        self.assertEqual(bars[0].buy_volume, 60.0)
        self.assertEqual(bars[0].sell_volume, 40.0)

    def test_empty_rows(self):
        self.assertEqual(rows_to_bars([], "BTCUSDT"), [])


    def test_closed_candle_filter_and_bad_rows(self):
        closed = [
            100, "1", "2", "0.5", "1.5", "100",
            120, "0", 10, "60", "0", "0"
        ]
        open_candle = [
            200, "1", "2", "0.5", "1.6", "100",
            200, "0", 10, "60", "0", "0"
        ]
        malformed = [
            "bad", "1", "2", "0.5", "1.5", "100",
            110, "0", 10, "60", "0", "0"
        ]

        bars = rows_to_bars(
            [closed, open_candle, malformed], "BTCUSDT", now_ms=150
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].ts, 100)
        self.assertEqual(bars[0].price, 1.5)

    def test_invalid_numeric_values_are_skipped(self):
        good = [
            100, "1", "2", "0.5", "1.5", "100",
            120, "0", 10, "60", "0", "0"
        ]
        bad_price = [
            200, "1", "2", "0.5", "nan", "100",
            120, "0", 10, "60", "0", "0"
        ]
        bad_volume = [
            300, "1", "2", "0.5", "1.5", "-1",
            120, "0", 10, "0", "0", "0"
        ]

        bars = rows_to_bars([bad_price, bad_volume, good], "BTCUSDT")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].price, 1.5)


    def test_download_paginates_when_open_candle_is_filtered(self):
        def row(ts, close_time, close_price="1.5"):
            return [
                ts, "1", "2", "0.5", close_price, "100",
                close_time, "0", 10, "60", "0", "0"
            ]

        first_page = [
            row(100, 120),
            row(200, 220),
            row(300, 1000),
        ]
        second_page = [row(50, 70)]

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "pagination-test.jsonl"
            with (
                patch("mi_core.real_data.time.time", return_value=1.0),
                patch(
                    "mi_core.real_data.fetch_klines",
                    side_effect=[first_page, second_page],
                ) as fetch,
                patch("mi_core.real_data.time.sleep"),
            ):
                bars, saved_path = download(
                    symbol="BTCUSDT",
                    interval="1h",
                    bars=3,
                    out=str(output),
                    sleep_s=0,
                )

            self.assertEqual([bar.ts for bar in bars], [50, 100, 200])
            self.assertEqual(len(bars), 3)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(saved_path, output)
            self.assertEqual(
                len(output.read_text(encoding="utf-8").splitlines()), 3
            )

if __name__ == "__main__":
    unittest.main()
