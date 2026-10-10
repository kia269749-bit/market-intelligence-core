"""Run the research-only CSCV probability-of-backtest-overfitting diagnostic.

Input JSON format:
{
  "returns_by_strategy": {
    "strategy_a": [0.01, -0.02, ...],
    "strategy_b": [0.02, 0.00, ...]
  },
  "n_blocks": 8
}
Returns must be aligned per-period net returns after realistic trading costs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.pbo import estimate_pbo_cscv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON containing aligned strategy return series")
    parser.add_argument("--out", required=True, help="Path for JSON report")
    parser.add_argument("--blocks", type=int, default=None, help="Even number of contiguous CSCV blocks (default: input value or 8)")
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    returns = source.get("returns_by_strategy")
    if not isinstance(returns, dict):
        parser.error("input must contain an object named returns_by_strategy")
    n_blocks = args.blocks if args.blocks is not None else int(source.get("n_blocks", 8))
    report = estimate_pbo_cscv(returns, n_blocks=n_blocks)
    report["input_file"] = str(Path(args.input))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "split_results"}, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
