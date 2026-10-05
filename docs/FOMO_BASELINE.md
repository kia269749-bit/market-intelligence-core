# FOMO Historical Baseline

This module builds a lightweight, deterministic baseline for FOMO/Meme detection.

Signals:
- Z-score: primary abnormal-volume gate.
- Percentile: contextual information only.
- Acceleration: second-difference context.
- Price/volume divergence: contextual risk/quality signal.
- FOMO score: bounded 0..1 composite.

A volume observation is marked abnormal only when its Z-score reaches the configured threshold (default 2.0). Percentile or acceleration alone cannot trigger abnormality.

The module is read-only and contains no network, order execution, exchange control, or service-control logic.
