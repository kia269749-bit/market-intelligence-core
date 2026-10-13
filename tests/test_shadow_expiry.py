import json
import tempfile
import unittest
from pathlib import Path

from mi_core.paper_journal import resolve_open_signals, summarize
from mi_core.shadow_performance import summarize_performance


class ShadowExpiryTests(unittest.TestCase):
    def _write_jsonl(self, path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        return str(path)

    def _signal(self, asset="BTC", horizon=2, forecast_ts=100):
        return {
            "status": "OPEN",
            "asset": asset,
            "direction": "BULLISH",
            "entry_price": 100.0,
            "stop": 95.0,
            "target": 110.0,
            "capital_usd": 500.0,
            "round_trip_cost_pct": 0.35,
            "horizon_bars": horizon,
            "forecast_ts": forecast_ts,
        }

    def test_expiry_counts_unique_asset_specific_samples(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / "shadow.jsonl"
            market = root / "market.jsonl"

            eth_signal = self._signal("ETH")
            eth_signal.update({
                "entry_price": 50.0,
                "stop": 45.0,
                "target": 60.0,
            })
            self._write_jsonl(journal, [
                self._signal("BTC"),
                eth_signal,
            ])
            self._write_jsonl(market, [
                {"timestamp": 100, "coins": {
                    "BTC": {"price": 100}, "ETH": {"price": 50}}},
                {"timestamp": 101, "coins": {
                    "BTC": {"price": 101}, "ETH": {"price": 51}}},
                {"timestamp": 101, "coins": {
                    "BTC": {"price": 101}, "ETH": {"price": 51}}},
                {"timestamp": 102, "coins": {
                    "BTC": {"price": 101}}},
            ])

            changed = resolve_open_signals(
                str(journal), {"BTC": 101.0, "ETH": 51.0},
                now=200, project60_path=str(market),
            )
            rows = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]
            by_asset = {row["asset"]: row for row in rows}

            self.assertEqual(changed, 1)
            self.assertEqual(by_asset["BTC"]["status"], "EXPIRED")
            self.assertEqual(by_asset["BTC"]["bars_elapsed"], 2)
            self.assertEqual(
                by_asset["BTC"]["exit_price_model"],
                "time_exit_observed_price",
            )
            self.assertAlmostEqual(by_asset["BTC"]["net_profit_usd"], 3.25)
            self.assertEqual(by_asset["ETH"]["status"], "OPEN")

            summary = summarize(str(journal))
            self.assertEqual(summary["expired"], 1)
            self.assertEqual(summary["open"], 1)
            self.assertEqual(summary["resolved"], 0)
            self.assertAlmostEqual(summary["net_profit_usd"], 3.25)

    def test_target_takes_priority_over_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / "shadow.jsonl"
            market = root / "market.jsonl"

            self._write_jsonl(journal, [self._signal()])
            self._write_jsonl(market, [
                {"timestamp": 100, "coins": {"BTC": {"price": 100}}},
                {"timestamp": 101, "coins": {"BTC": {"price": 110}}},
                {"timestamp": 102, "coins": {"BTC": {"price": 110}}},
            ])

            changed = resolve_open_signals(
                str(journal), {"BTC": 110.0},
                now=200, project60_path=str(market),
            )
            row = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])

            self.assertEqual(changed, 1)
            self.assertEqual(row["status"], "TARGET")
            self.assertEqual(row["exit_price"], 110.0)

    def test_expired_pnl_counts_but_expiry_is_not_a_win_or_loss(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "shadow.jsonl"
            self._write_jsonl(journal, [
                {"status": "TARGET", "net_profit_usd": 5.0},
                {"status": "STOP", "net_profit_usd": -2.0},
                {"status": "EXPIRED", "net_profit_usd": -3.0},
                {"status": "OPEN", "net_profit_usd": 999.0},
            ])

            summary = summarize(str(journal))
            self.assertEqual(summary["resolved"], 2)
            self.assertEqual(summary["closed"], 3)
            self.assertEqual(summary["expired"], 1)
            self.assertEqual(summary["wins"], 1)
            self.assertEqual(summary["losses"], 1)
            self.assertEqual(summary["win_rate"], 0.5)
            self.assertEqual(summary["net_profit_usd"], 0.0)

            performance = summarize_performance(str(journal))
            self.assertEqual(performance["resolved"], 2)
            self.assertEqual(performance["closed"], 3)
            self.assertEqual(performance["expired"], 1)
            self.assertEqual(performance["wins"], 1)
            self.assertEqual(performance["losses"], 1)
            self.assertEqual(performance["net_profit_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
