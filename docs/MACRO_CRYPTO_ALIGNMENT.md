# Macro/Crypto Time Alignment

The macro layer must never introduce lookahead bias. `align_previous` selects only the latest macro observation whose timestamp is less than or equal to the crypto bar timestamp. A configurable maximum age can reject stale observations.

This module is deterministic and network-free. It is intended to sit between public economic data adapters such as FRED and the cross-asset regime layer.

The alignment is research-only: no orders, credentials, or Termux service controls are involved.
