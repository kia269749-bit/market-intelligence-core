# TP1 / TP2 / TP3 path diagnostics

Run against the local Project60 JSONL history:

```bash
clear
cd ~/market-intelligence-core
python -m mi_core.tp_path_validation --input "$HOME/institutional-flow/history/market.jsonl" --top 3 --max-rows 800 --horizons 5,15,60 --targets 1.15,1.75,2.35 --cost 0.35 --out reports/tp_path_5_15_60.json
```

The default gross price targets are 1.15%, 1.75%, and 2.35%. With the default 0.35% round-trip cost, these correspond to approximate net moves of 0.80%, 1.40%, and 2.00%, respectively, before any additional execution differences. They are diagnostic defaults and should be replaced if the project's established TP policy differs.

The report estimates favorable excursion using the one-minute snapshot closes. It can miss intraminute high/low touches and does not simulate stop-loss ordering, partial exits, fills, or a complete TP/SL trade ledger. Therefore TP counts alone are not proof of profitability. Compare net return at each horizon and then run a first-touch TP/SL simulator with exchange costs before promoting a strategy.
