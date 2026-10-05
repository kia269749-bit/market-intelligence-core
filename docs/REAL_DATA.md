# Real Market Data Mode

The real-data command is intentionally research-only.

## Source

The default adapter uses Binance's public spot klines endpoint through `data-api.binance.vision`. No API key or account permission is required for public market data.

## Normalization

Each kline becomes a `MarketBar`:

- `ts`: kline open time in milliseconds
- `price`: close price
- `volume`: base-asset volume
- `buy_volume`: taker-buy base volume
- `sell_volume`: total volume minus taker-buy volume

The current spot adapter does not invent open interest, funding, whale-wallet identity, or sentiment. Those fields remain unavailable/zero until a dedicated public-data adapter is added.

## Historical retrieval

The adapter paginates backward in chunks of at most 1000 bars, deduplicates timestamps, sorts chronologically, and writes the requested tail to JSONL.

## Safety boundary

This mode never submits orders, never reads exchange account state, and never stores API credentials. Its output is for historical research, backtesting, OOS validation and shadow analysis only.
