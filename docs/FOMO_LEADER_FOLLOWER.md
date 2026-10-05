# FOMO Leader -> Follower Detection

Research-only detection of short-lag trader clusters on the same token.

A leader must have a configured historical leader score above the gate and a reliable fill direction. Followers must trade the same token in the same direction within the configured time window and meet the fill-confidence gate.

The result includes follower count, follower volume, median lag, and a conservative confidence score.

This is correlation evidence, not proof that one wallet caused another wallet to trade.
