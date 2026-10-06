# Live signal execution

This runner executes the **research signal pipeline** continuously on the phone:
Project 60 snapshot + public market data + FOMO scanner + optional validated Leader/Follower evidence -> Market Brain -> Persian report.

It does not place orders, hold credentials, sign transactions, or control legacy services.

Recommended phone interval: 60 seconds.
Minimum enforced interval: 30 seconds.

Example:
python tools/live_signal_runner.py --project60-file ~/institutional-flow/history/market.jsonl --interval 60
