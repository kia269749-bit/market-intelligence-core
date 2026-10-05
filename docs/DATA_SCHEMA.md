# Market Data Schema

CSV/JSONL observations:
ts,symbol,price,volume,oi,funding,bid,ask,buy_volume,sell_volume,whale_buy,whale_sell,sentiment

Required: ts, symbol, price.
Optional fields default to zero or None.
Timestamps must be chronological within each symbol. Raw data should be append-only. Malformed records must be rejected or quarantined before research.
