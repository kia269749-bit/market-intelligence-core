"""Append-only outcome journal for per-specialist win-rate learning."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

class OutcomeStore:
    def __init__(self, path: str | Path): self.path = Path(path)
    def append(self, record: dict[str, Any]) -> None:
        required = ("signal_id", "brain_id", "family", "symbol", "direction", "resolved", "won")
        missing = [key for key in required if key not in record]
        if missing: raise ValueError("missing outcome fields: " + ",".join(missing))
        if record["direction"] not in ("LONG", "SHORT"): raise ValueError("only directional signals can resolve")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + chr(10))
    def performance(self, brain_id: str, symbol: str | None = None,
                    timeframe: str | None = None, regime: str | None = None) -> dict[str, int]:
        """Return this brain's resolved record, optionally scoped to context."""
        wins = losses = 0
        if not self.path.exists(): return {"wins": 0, "losses": 0}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try: row = json.loads(line)
                except json.JSONDecodeError: continue
                if row.get("brain_id") != brain_id or not row.get("resolved"): continue
                if symbol is not None and row.get("symbol") != symbol: continue
                if timeframe is not None and row.get("timeframe") != timeframe: continue
                if regime is not None and row.get("regime") != regime: continue
                if row.get("won") is True: wins += 1
                elif row.get("won") is False: losses += 1
        return {"wins": wins, "losses": losses}


    def resolve_due_signals(self, signal_path: str | Path, current_prices: dict[str, float],
                             now_ms: int, round_trip_cost_pct: float = 0.12) -> int:
        """Resolve directional specialist calls after one timeframe horizon.

        This is a fixed-horizon signal classification, not a simulated limit
        order or TP/SL fill. The binary win is net directional price movement
        after the configured round-trip cost.
        """
        import math
        from .signal_journal import _TIMEFRAME_MS

        signal_file = Path(signal_path)
        if not signal_file.exists():
            return 0
        resolved_ids = set()
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                        if row.get("resolved"):
                            resolved_ids.add(str(row.get("signal_id")))
                    except json.JSONDecodeError:
                        continue
        added = 0
        with signal_file.open("r", encoding="utf-8") as handle:
            signals = [json.loads(line) for line in handle if line.strip()]
        for signal in signals:
            signal_id = str(signal.get("signal_id", ""))
            if (not signal_id or signal_id in resolved_ids or signal.get("direction") not in ("LONG", "SHORT")
                    or not signal.get("available")):
                continue
            symbol = str(signal.get("symbol", "")).upper()
            try:
                entry = float(signal["entry_price"])
                as_of = int(signal["as_of_ms"])
                timeframe = str(signal.get("brain_id", "")).rsplit(".", 1)[-1]
                horizon = _TIMEFRAME_MS.get(timeframe, _TIMEFRAME_MS.get(str(signal.get("timeframe")), 3_600_000))
                current = float(current_prices[symbol])
                cost = float(round_trip_cost_pct)
            except (KeyError, TypeError, ValueError):
                continue
            if (not all(math.isfinite(x) for x in (entry, current, cost))
                    or entry <= 0 or current <= 0 or cost < 0
                    or now_ms - as_of < horizon):
                continue
            gross = ((current / entry) - 1.0) * 100.0
            if signal["direction"] == "SHORT":
                gross = -gross
            net = gross - cost
            self.append({
                "signal_id": signal_id,
                "brain_id": signal["brain_id"],
                "family": signal["family"],
                "symbol": symbol,
                "timeframe": signal.get("timeframe"),
                "regime": signal.get("regime"),
                "direction": signal["direction"],
                "resolved": True,
                "won": net > 0.0,
                "entry_price": entry,
                "exit_price": current,
                "gross_move_pct": round(gross, 6),
                "net_move_pct": round(net, 6),
                "round_trip_cost_pct": cost,
                "resolved_ts_ms": int(now_ms),
                "outcome_method": "fixed_horizon_directional_return",
            })
            resolved_ids.add(signal_id)
            added += 1
        return added
