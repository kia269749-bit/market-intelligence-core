# Macro Context Bundle

This module is the small integration boundary between time-aligned economic data and the existing cross-asset regime/signal gate.

The intended flow is:

FRED/public data -> point-in-time alignment -> decimal returns -> `snapshot_from_aligned` -> cross-asset regime -> diagnostic macro signal quality context.

It does not fetch data itself, does not select future observations, and does not override profitability or risk gates. All inputs are validated as decimal returns within +/-100%.
