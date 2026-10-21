# Historical Macro/Crypto Replay

`replay_macro_context` evaluates already-collected macro returns at each crypto bar timestamp.

Rules:
- Only the latest observation at or before the crypto timestamp is eligible.
- A maximum age can reject stale observations.
- Missing macro streams produce an explicit stale row rather than fabricated data.
- No network access occurs during replay.

This is the measurement layer needed before evaluating whether macro context improves signal quality or trading outcomes. It does not place orders and does not alter risk gates.
