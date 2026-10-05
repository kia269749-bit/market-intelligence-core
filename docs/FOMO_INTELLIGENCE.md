# FOMO Intelligence Integration

This layer connects market FOMO detection with historical trader confidence.

A research flag requires two independent conditions:
1. A statistically abnormal market-volume event.
2. A historically eligible trader profile above the configured confidence threshold.

Historical trader confidence can strengthen an event score, but trader history alone cannot create a market event. This prevents leaderboard persistence from becoming a standalone trading trigger.
