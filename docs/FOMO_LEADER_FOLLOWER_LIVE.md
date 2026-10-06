# FOMO Leader -> Follower live evidence

The live brain can consume a read-only JSONL stream of validated public fills plus a JSON leader-score map.

Flow:

public chain data -> validated TraderFill -> leader score -> leader/follower cluster -> Market Brain evidence

The bridge requires:
- trader identity/address present in the validated fill
- BUY/SELL direction
- timestamp
- positive trade size
- confidence >= 0.70
- leader score >= 0.60
- at least 2 distinct followers within the configured 300-second window

This is correlation evidence, not proof that the leader caused the followers.

The system remains research-only and never signs, submits, or manages trades.

CLI:
python -m mi_core.cli live-all --project60-file <market.jsonl> --fomo-fills-file <fills.jsonl> --fomo-leader-scores <scores.json>
