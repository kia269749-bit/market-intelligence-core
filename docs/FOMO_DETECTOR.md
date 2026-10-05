# FOMO Event Detection

The detector converts the historical baseline into a conservative FOMO event.

Rules:
- A Z-score threshold is the trigger.
- Trader persistence can increase confidence but can never create an event by itself.
- Output is a typed, serializable event candidate and performs no execution.
- No network access is performed by the detector.
