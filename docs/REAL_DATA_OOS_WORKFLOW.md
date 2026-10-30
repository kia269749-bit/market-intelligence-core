# Real-data OOS workflow and LBank source boundary

## Important venue distinction

The documented LBank CONTRACT REST API is hosted at `https://lbkperp.lbank.com/`.
Its documented public endpoints include contract instruments, current contract
market quotes, and order-book depth. The published contract API reference does
not document a historical OHLC/K-line endpoint.

The downloader in `mi_core/fetch_lbank_spot_klines.py` therefore uses the
documented public SPOT endpoint `GET https://api.lbank.info/v2/kline.do`.
It writes real LBank spot candles and labels every row as
`source=lbank_spot_public_kline` and `market_type=spot`. This data must not be
described as LBank Futures data and must not be silently mixed with
Hyperliquid perpetuals or Project60 derivatives data.

Example:
```bash
python -m mi_core.fetch_lbank_spot_klines --symbol btc_usdt --interval 1h --limit 1000 --out data/lbank_spot_btc_1h.jsonl
```

Supported intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1d. The public API documents
1-2000 candles per request. The script validates OHLC consistency, timestamp
uniqueness, and writes Project60-loader-compatible price fields plus OHLCV
provenance. The current Project60 loader consumes close price; OHLC fields are
retained but not used by the existing forecasting model.

## OOS comparison

`mi_core.oos_benchmark.compare_oos_baselines` compares forecast direction,
long-only buy-and-hold over the same non-overlapping forward windows, and a
seeded random-direction baseline. It deducts the selected central research
cost policy exactly once per completed round trip. It reports net USD PnL,
maximum drawdown, win rate, and per-trade Sharpe (not annualized).

The real validation runner emits both `base` (0.15%) and `strict` (0.45%)
benchmark scenarios for each asset/horizon. These percentages are research
stress assumptions, not verified LBank fee schedules. Actual maker/taker fees,
spread, slippage and market impact must be measured separately before any
execution-cost claim.

A result is not evidence of a tradable edge unless the input is real, correctly
timestamped, sufficiently long, and venue/market-type matched. Report sample
counts and data provenance. No live orders are supported by this workflow.
