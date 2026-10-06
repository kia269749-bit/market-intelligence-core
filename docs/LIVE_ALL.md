# Live execution architecture

- Project 60 remains the specialist for order-book/OI/funding/trade-flow evidence.
- FOMO now has a public-market live scanner for meme momentum and buy/sell pressure.
- Market Brain combines live evidence and remains research-only.
- No exchange credentials, signing, order placement, or legacy-service control is used.

FOMO reports wallet_level=false because wallet-level leader/follower evidence needs reliable chain fills with trader IDs.

Run: python -m mi_core.cli live-all --interval 30 --fomo-chain solana

For a true three-source deployment, Project 60 snapshots should be exported read-only into a shared append-only evidence file. The coordinator never modifies or restarts protected Termux services.
