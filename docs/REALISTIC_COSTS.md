# Realistic Execution Cost Engine

The validation pipeline must not treat raw price movement as tradable profit.

`mi_core.costs` separates the main execution-cost assumptions:
- taker fee
- bid/ask spread
- market slippage
- market-impact allowance

Inputs are expressed in basis points (bps) **per side**. The estimate is round-trip:
entry and exit fees are both charged, and spread, slippage, and impact are modeled on both fills. The result is a transparent `ExecutionCost` object with every component and the total.

## Design rules

1. Costs are explicit, deterministic and testable.
2. No exchange credentials or live orders are required.
3. No future information is used.
4. The engine is research-only.
5. Backtests report net PnL and include all modeled friction in trade-level cost totals.
6. Central assumptions are read from `config/default.json`; explicit per-call overrides remain possible for controlled scenario tests.

## Central LBank Futures research assumptions

The current default profile is LBank USDT-margined futures:
- taker fee: 6 bps per side (published default, not account-tier verified)
- maker fee: 2 bps per side (published default, not account-tier verified)
- spread allowance: 2 bps per side
- slippage allowance: 3 bps per side
- impact allowance: 1 bp per side

With taker execution, the modeled round-trip total is 24 bps, or 0.24% of notional, before funding and any additional venue/account-specific charges. These are explicit research assumptions, not a guarantee of realized costs. The user's account fee tier has not been verified.

## Validation requirements

Cost assumptions must be fixed in the research protocol and applied unchanged to the corresponding out-of-sample period unless a documented scenario test is being run. Strategy reports must distinguish gross movement, fees, spread, slippage, impact, funding, and net outcome where data permits.
