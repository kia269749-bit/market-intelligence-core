# FRED Economic Data Adapter

This adapter provides a controlled path from FRED observations into the cross-asset research layer.

## Supported flow

1. Set FRED_API_KEY outside the repository.
2. Fetch one or more FRED series with fetch_series.
3. Convert observations to date-keyed returns with align_daily_series.
4. Combine those returns with crypto daily data before calling the cross-asset regime layer.

The adapter skips FRED missing-value markers and does not forward-fill missing dates. This prevents stale macro observations from silently masquerading as fresh information.

FRED's observations endpoint supports JSON and observation-date filtering. The FRED API requires a registered API key for programmatic access.

No credentials are committed, no orders are placed, and no Termux services are controlled.
