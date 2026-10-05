# Market Intelligence Core

Auditable crypto market intelligence and research engine.

Pipeline:
Collectors -> Raw Append-Only Data -> Normalization -> Features -> Flow/Smart Money/FOMO -> Regime -> Signals -> Validation -> Backtest/WFO/OOS/Monte Carlo -> Risk/Profitability Gate -> Shadow Trading -> Outcome Memory -> Reports/Dashboard.

## Real multi-exchange mode

The project now has a low-load public-market-data monitor for **Binance, Coinbase, Kraken and OKX**. The default universe includes BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, LINK and TRX. More supported symbols can be passed at runtime.

```bash
python -m mi_core.cli live --exchanges binance,coinbase,kraken,okx --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT --interval 20
```

Each cycle prints the real timestamp, median price across available exchanges, observed price range, cross-exchange spread, source count and warnings. This is **research/paper analysis only**. It never places orders and never uses exchange credentials.

## Historical real-data research

```bash
python -m mi_core.cli real --symbol BTCUSDT --interval 1h --bars 5000
python -m mi_core.cli dashboard --report reports/real_btcusdt_1h.json
```

## Termux

The live monitor is intentionally separate from the user's existing Termux services. It does not control or modify them.

```bash
clear
cd ~
git clone https://github.com/kia269749-bit/market-intelligence-core.git
cd market-intelligence-core
PYTHONUNBUFFERED=1 python -m mi_core.cli live --interval 20
```

Press Ctrl+C to stop the foreground monitor.

## Quick start

```bash
python -m unittest discover -s tests -v
python -m mi_core.cli demo --out data/demo
python -m mi_core.cli analyze --input data/demo/market.jsonl
```

See `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `docs/DATA_SCHEMA.md`, `docs/TERMUX_LIVE.md` and `config/markets.json`.
