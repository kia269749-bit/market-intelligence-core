# Shadow Trading and Outcome Memory

This stage records signals and later outcomes without placing real orders.

## Rules
- Every signal has a unique ID.
- Outcomes must reference a known signal.
- Outcomes must occur strictly after the signal timestamp.
- No exchange credentials or order endpoints are used.
- Summary metrics are descriptive and do not imply future profitability.

The outcome memory can later be used for regime-specific edge analysis, signal decay analysis, and calibration. This stage does not modify the existing Termux services.
