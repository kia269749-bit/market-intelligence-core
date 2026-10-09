# TP ladder strategy tournament

Run locally on Project60 JSONL data (read-only input; report output only):

```bash
clear
cd ~/market-intelligence-core || exit 1
python -m mi_core.tp_execution_backtest \
  --input "$HOME/institutional-flow/history/market.jsonl" \
  --max-rows 800 --horizons 5,15,60 \
  --targets 1.15,1.75,2.35 --stop 0.75 --cost 0.35 \
  --min-trades 10 --out reports/tp_tournament_5_15_60.json
```

The tournament compares trend-only, flow-only, 2-of-3 vote, and unanimous-vote variants. It chooses a candidate only from the middle chronological segment and then checks that chosen strategy on the final, untouched 20% segment. A strategy is a shadow candidate only if it has at least the configured number of trades and positive net result/expectancy in both selection and holdout segments.

The TP ladder allocates one third of position exposure to each TP level. A stop closes the remaining exposure. One position at a time prevents overlapping trade counting. Round-trip costs are charged once per trade. Results are approximate because the current Project60 JSONL loader provides snapshots rather than candle OHLC; this cannot reliably resolve all intrabar TP/SL ordering or actual fills. No orders are placed.

The third vote is a trade-flow confirmation proxy, not FOMO wallet intelligence. Do not describe it as smart-money consensus until wallet-level data is connected and validated.
