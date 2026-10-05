# Market Intelligence Core

Auditable crypto market intelligence and research engine.

Pipeline:
Collectors -> Raw Append-Only Data -> Normalization -> Features -> Flow/Smart Money/FOMO -> Regime -> Signals -> Validation -> Backtest/WFO/OOS/Monte Carlo -> Risk/Profitability Gate -> Shadow Trading -> Outcome Memory -> Reports/Dashboard.

## Research modes

**Real market data mode** downloads public historical Binance spot klines without API keys, stores the normalized bars locally as append-only JSONL, then runs the same chronological train/test, cost-aware backtest, Monte Carlo and profitability-gate pipeline used by file-based research. Binance documents its public market-data endpoints and millisecond timestamps in its API documentation: https://developers.binance.com/en/docs/products/derivatives-trading-portfolio-margin-pro/general-info

Example:

```bash
python -m mi_core.cli real --symbol BTCUSDT --interval 1h --bars 5000
python -m mi_core.cli dashboard --report reports/real_btcusdt_1h.json
```

The real-data path is **research/paper analysis only**. It does not place orders, hold credentials, or connect to an exchange account.

## Design

- Deterministic and testable Python 3.11+.
- Standard library only for the core engine.
- Raw observations are append-only JSONL.
- Backtests model fees, slippage and latency assumptions.
- Training and evaluation windows are separated.
- Signals are explainable and serializable.
- No exchange keys are required for research mode.
- Real-data ingestion validates and deduplicates timestamps before analysis.

## Quick start

```bash
python -m mi_core.cli demo --out data/demo
python -m mi_core.cli analyze --input data/demo/market.jsonl
python -m mi_core.cli real --symbol BTCUSDT --interval 1h --bars 1000
python -m unittest discover -s tests -v
```

See `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `docs/DATA_SCHEMA.md` and `config/default.json`.
