# Historical daily-asset availability audit

Source: actual `daily-multiyear-coverage` artifact from [coverage workflow run #5](https://github.com/kia269749-bit/market-intelligence-core/actions/runs/38353134881), artifact ID `11791697523`. Venue: Binance public spot klines, interval `1d`. Source report status: `ok`; 30/30 symbols have data. Last complete candle: `2026-10-12` UTC; current UTC-day candle excluded.

Availability count means the number of audited symbols whose reported `[first_date_utc, last_complete_date_utc]` overlaps any part of that calendar period. It is **not** a count of symbols available for every day of that period, and it is not a performance result.

## Annual availability

| Year | Symbols with any reported coverage | Universe size |
|---:|---:|---:|
| 2020 | 20 | 30 |
| 2021 | 22 | 30 |
| 2022 | 24 | 30 |
| 2023 | 29 | 30 |
| 2024 | 30 | 30 |
| 2025 | 30 | 30 |
| 2026 | 30 | 30 |

## Monthly availability

| Month (UTC) | Symbols with any reported coverage | Universe size |
|---|---:|---:|
| 2020-10 | 20 | 30 |
| 2020-11 | 20 | 30 |
| 2020-12 | 20 | 30 |
| 2021-01 | 20 | 30 |
| 2021-02 | 20 | 30 |
| 2021-03 | 20 | 30 |
| 2021-04 | 20 | 30 |
| 2021-05 | 22 | 30 |
| 2021-06 | 22 | 30 |
| 2021-07 | 22 | 30 |
| 2021-08 | 22 | 30 |
| 2021-09 | 22 | 30 |
| 2021-10 | 22 | 30 |
| 2021-11 | 22 | 30 |
| 2021-12 | 22 | 30 |
| 2022-01 | 22 | 30 |
| 2022-02 | 22 | 30 |
| 2022-03 | 22 | 30 |
| 2022-04 | 22 | 30 |
| 2022-05 | 22 | 30 |
| 2022-06 | 23 | 30 |
| 2022-07 | 23 | 30 |
| 2022-08 | 23 | 30 |
| 2022-09 | 23 | 30 |
| 2022-10 | 24 | 30 |
| 2022-11 | 24 | 30 |
| 2022-12 | 24 | 30 |
| 2023-01 | 24 | 30 |
| 2023-02 | 24 | 30 |
| 2023-03 | 25 | 30 |
| 2023-04 | 25 | 30 |
| 2023-05 | 27 | 30 |
| 2023-06 | 27 | 30 |
| 2023-07 | 27 | 30 |
| 2023-08 | 28 | 30 |
| 2023-09 | 28 | 30 |
| 2023-10 | 29 | 30 |
| 2023-11 | 29 | 30 |
| 2023-12 | 29 | 30 |
| 2024-01 | 29 | 30 |
| 2024-02 | 29 | 30 |
| 2024-03 | 29 | 30 |
| 2024-04 | 29 | 30 |
| 2024-05 | 29 | 30 |
| 2024-06 | 29 | 30 |
| 2024-07 | 30 | 30 |
| 2024-08 | 30 | 30 |
| 2024-09 | 30 | 30 |
| 2024-10 | 30 | 30 |
| 2024-11 | 30 | 30 |
| 2024-12 | 30 | 30 |
| 2025-01 | 30 | 30 |
| 2025-02 | 30 | 30 |
| 2025-03 | 30 | 30 |
| 2025-04 | 30 | 30 |
| 2025-05 | 30 | 30 |
| 2025-06 | 30 | 30 |
| 2025-07 | 30 | 30 |
| 2025-08 | 30 | 30 |
| 2025-09 | 30 | 30 |
| 2025-10 | 30 | 30 |
| 2025-11 | 30 | 30 |
| 2025-12 | 30 | 30 |
| 2026-01 | 30 | 30 |
| 2026-02 | 30 | 30 |
| 2026-03 | 30 | 30 |
| 2026-04 | 30 | 30 |
| 2026-05 | 30 | 30 |
| 2026-06 | 30 | 30 |
| 2026-07 | 30 | 30 |
| 2026-08 | 30 | 30 |
| 2026-09 | 30 | 30 |
| 2026-10 | 30 | 30 |

## Universe comparison

- **30-symbol universe:** see [`config/asset_universe_sets.json`](../config/asset_universe_sets.json).
- **22 symbols marked `five_year_history_available=true` by the raw audit:** BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, TRXUSDT, LINKUSDT, AVAXUSDT, BCHUSDT, LTCUSDT, DOTUSDT, UNIUSDT, ETCUSDT, NEARUSDT, ATOMUSDT, FILUSDT, ICPUSDT, INJUSDT, SHIBUSDT, AAVEUSDT.
- **8 symbols below the five-year threshold:** APTUSDT, ARBUSDT, OPUSDT, SUIUSDT, SEIUSDT, TIAUSDT, RENDERUSDT, PEPEUSDT.

The 22-symbol subset is a robustness comparison, not a cure for survivorship bias. The universe is selected from currently listed USDT spot pairs, so delisted, failed, renamed, or historically illiquid assets are underrepresented. Daily OHLC candles do not measure historical bid-ask spreads or realized slippage.

## Interpretation for locked holdout

These counts summarize **data coverage only**. They do not establish an economic edge, and they must not be used to tune strategy parameters against the final holdout. The Stage B date lock remains `2020-10-05` through `2026-10-12`, with development through `2025-07-29` and final holdout `2025-07-30` through `2026-10-12`.
