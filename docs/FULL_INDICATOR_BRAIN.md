# Full indicator and candlestick brain integration

Status: development foundation on a separate feature branch. Not merged or enabled for live execution.

- Pinned dependency: pandas-ta-classic 0.9.0.
- The engine discovers the installed accessor inventory and attempts every callable on supplied completed OHLCV bars.
- Native candlestick patterns are dispatched using the all-pattern mode.
- Successfully computed outputs are retained as machine-readable features.
- Only explicit causal interpretations and signed native candle-pattern outputs cast directional votes. Unmapped outputs remain available as model features; their meaning is not guessed.
- The result is a directional evidence object for fusion with forecast, regime, multi-timeframe, flow, data-quality and cost gates.
- The caller must supply chronological completed OHLCV bars. No data source is fabricated.
- Functions needing extra inputs or parameters are reported unavailable. Whole-series or non-causal functions must not be used as contemporaneous signals.
- Research-only; no orders, protected services, or forward-test files are changed.
- Existing EDGE_SEARCH_v1 and its 140-row TRIALS.json are untouched. This is a separate development track.
- Runtime tests have not yet been executed.
