# Source verification corrections

This file records corrections without rewriting the frozen Signal Lab trial lock.

- The frozen signal_lab/TRIALS.json originally marked GMGN unavailable after a connector-side 404. Later official-source discovery confirmed https://github.com/GMGNAI/gmgn-skills exists. The source catalog records it as a public MIT repository and the read-only adapter uses its documented public demo key. The old locked trial entry is historical and remains unchanged; it must not be interpreted as the current source-availability status.
- Repository existence, maintainer benchmark, adapter connectivity and a Project60 signal are four different facts. The mesh keeps them separate.
