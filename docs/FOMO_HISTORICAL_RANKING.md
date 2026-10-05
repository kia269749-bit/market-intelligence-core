# Historical FOMO Ranking

The historical ranker evaluates repeated leaderboard snapshots, not single lucky observations.

It rewards:
- persistent leaderboard rank
- positive PnL presence
- improving or stable PnL trend
- sustained volume
- sustained trading activity
- larger historical sample size

## Rank normalization

Leaderboard rank is normalized against a stable max_rank ceiling rather than the trader's own worst observed rank. This prevents a trader who is always ranked #5 from being treated as equivalent to a trader who is always ranked #1.

The default max_rank is 150, matching the largest documented leaderboard limit. It can be overridden when the source has a smaller or different fixed ceiling.

## Sample confidence

min_snapshots defaults to 3. This is the entry gate. A separate sample_confidence score rises with additional observations and reaches 1.0 at 12 snapshots.

## Important limitation

This is a historical persistence score, not proof of trading skill and not a trading signal. Leaderboard PnL, volume and trade counts are aggregate observations. They are not reconstructed individual trades.

Trade-level performance such as ROI, win rate, drawdown, early entry and clean exit should only be added when reliable historical trade data is available.
