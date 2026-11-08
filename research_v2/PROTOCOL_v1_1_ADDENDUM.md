# Addendum v1.1 to Trend Strategy Research Protocol v1

Date: 2026-10-18

Status: This addendum supplements v1. The original v1 file remains unchanged.
Original v1 SHA-256:
b2d04224d3f9cd970dcee2a9d194ff79f876614bb5c0db94aa320ba5437ef7a9

## 1. Correction about period C

Period C (2025-01-01 through 2026-10-10) is NOT sealed. Earlier exploratory
tools (test_donchian_long_oos, ema_settings_oos, compare_donchian_exits) already
ran the same Donchian/EMA families on the same BTC/ETH data and printed results
for 2025-2026. C is therefore exploratory/informational only and is not an
independent final test. The six v1 candidates were also chosen after earlier results.

## 2. Consequences

- Candidate screening uses A and B only, with prior-exposure limitations disclosed.
- Results on C may be reported but cannot be counted as final independent evidence.
- Final evidence requires coins with a documented no-prior-exposure audit and/or
  prospective forward paper testing with frozen rules.
- The candidate coin universe must be fixed before downloading its data or
  inspecting strategy results. No coin list is approved by this addendum.
- No coin is approved as unseen or independent until prior exposure is audited.

## 3. Data audit result (2026-10-18)

- 1d BTC/ETH: 2019-01-01 to 2026-10-10, 2840 rows per file, no timestamp gaps,
  duplicates, invalid timestamps, or backwards adjacent timestamps.
- 4h BTC/ETH: 2020-01-01 to 2026-10-11 12:00 UTC, 14853 rows per file,
  no duplicates, invalid timestamps, or backwards adjacent timestamps.
- One missing 4h candle per asset on 2020-02-19, between 08:00 and 16:00 UTC.
  This gap is not filled with a synthetic candle.
- The 4h files have no pre-A warm-up history. Early-2020 periods without enough
  indicator history must not emit signals and this limitation must be reported.
- This audit establishes timestamp continuity and basic file integrity only.
  OHLC plausibility and extreme returns require a separate audit before backtesting.
