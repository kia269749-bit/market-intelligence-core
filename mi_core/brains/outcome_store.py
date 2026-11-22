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
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\\n")
    def performance(self, brain_id: str) -> dict[str, int]:
        wins = losses = 0
        if not self.path.exists(): return {"wins": 0, "losses": 0}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try: row = json.loads(line)
                except json.JSONDecodeError: continue
                if row.get("brain_id") != brain_id or not row.get("resolved"): continue
                if row.get("won") is True: wins += 1
                elif row.get("won") is False: losses += 1
        return {"wins": wins, "losses": losses}
