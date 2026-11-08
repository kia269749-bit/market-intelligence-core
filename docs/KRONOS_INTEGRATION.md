# Kronos integration (research-only)

## What is integrated

Project60 uses the official upstream Kronos implementation as an optional OHLCV foundation-model provider. The adapter lives in `mi_core/kronos_adapter.py` and loads the upstream checkout lazily. No upstream model code or weights are copied into this repository.

- Supported checkpoints: `NeoQuasar/Kronos-mini`, `NeoQuasar/Kronos-small`, and `NeoQuasar/Kronos-base`.
- Mini uses the 2k tokenizer and up to 2048 context bars; Small/Base use the base tokenizer and 512 context bars.
- The adapter generates independent sampled paths in bounded batches (up to 100 paths), rather than treating the upstream predictor's averaged `sample_count` output as separate scenarios.
- Output includes OHLCV paths and descriptive p10/median/p90 summaries.
- Scenario frequency is **not** a calibrated probability and is not a trading signal.

## Data contract

Kronos requires explicit, completed OHLC bars. Project60 price-only snapshots are not converted into fake OHLC bars. Missing open/high/low values cause a closed failure with `missing_ohlc`. Timestamps must be strictly increasing and every bar interval must exactly match the configured interval. Gaps or irregular bars are rejected. Use UTC timestamps.

## Optional dependencies and upstream checkout

1. Clone the official repository separately: https://github.com/shiyu-coder/Kronos
2. Install its documented requirements in an isolated environment. The upstream implementation requires PyTorch, pandas, Hugging Face Hub, and tqdm.
3. From the Market Intelligence Core checkout, install the optional adapter dependencies with `python -m pip install -e ".[kronos]"`.
4. Install any additional packages listed by the pinned upstream Kronos `requirements.txt` in the same isolated environment.
5. Download model weights only after choosing a checkpoint and checking storage/RAM.
6. Configure `KronosConfig(repo_path=...)` with the local upstream checkout path.

## Optional Market Brain invocation

After the upstream checkout and optional dependencies are installed, enable the evidence-only integration explicitly:

```bash
KRONOS_REPO_PATH="$HOME/Kronos" python -m mi_core.cli live-all \
  --project60-file data/project60.jsonl \
  --kronos-enabled \
  --kronos-model NeoQuasar/Kronos-mini \
  --kronos-scenarios 20 \
  --kronos-batch-size 2 \
  --kronos-pred-len 24 \
  --kronos-interval-minutes 60
```

The CLI defaults to Kronos disabled. If the Project60 file contains only snapshot prices and lacks explicit open/high/low/close fields, the adapter reports unavailable and does not invent candle values. The current Market Brain displays Kronos output separately; it does not use it to make the system actionable.


Do not install PyTorch into the user's existing Termux environment as part of this code change. Benchmark on a disposable environment first; CPU inference may be slow and Android/PyTorch wheel support varies.

## Brain integration boundary

The Market Brain records Kronos output as a separate evidence source. It does not add Kronos scenario frequency to fusion votes, confidence, execution readiness, shadow eligibility, or Outcome Memory. This remains true until a frozen, independent OOS protocol demonstrates calibrated probabilities and positive net expectancy after the centralized 0.15% base and 0.45% strict round-trip cost policies.

## Upstream provenance

- Project: https://github.com/shiyu-coder/Kronos
- Paper: https://arxiv.org/abs/2508.02739
- License: MIT (retain upstream copyright/license notices when copying any upstream source; this integration imports the upstream checkout and does not vendor its code).
