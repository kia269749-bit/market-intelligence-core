# Market Intelligence Core

Auditable crypto market intelligence engine.

Pipeline:
Collectors -> Raw Append-Only Data -> Normalization -> Features -> Flow/Smart Money/FOMO -> Regime -> Signals -> Validation -> Backtest/WFO/OOS/Monte Carlo -> Risk/Profitability Gate -> Shadow Trading -> Outcome Memory -> Reports/Dashboard.

Design:
- Deterministic and testable Python 3.11+.
- Standard library only for the core engine.
- Raw observations are append-only JSONL.
- Backtests model fees, slippage and latency assumptions.
- Training and evaluation windows are separated.
- Signals are explainable and serializable.
- No exchange keys are required for research mode.

Quick start:
python -m mi_core.cli demo --out data/demo
python -m mi_core.cli analyze --input data/demo/market.jsonl
python -m unittest discover -s tests -v

See docs/ARCHITECTURE.md and config/default.json.
