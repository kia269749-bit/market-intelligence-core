# FOMO public multi-source collector

This layer is read-only and API-key-free.

Sources:
- Solana public RPC for signatures, confirmed transactions, and SPL token balance deltas.
- DEX Screener public API for token discovery, boosts, pairs, price/volume/liquidity context.
- GeckoTerminal Public API for independent DEX/pool confirmation.
- Hyperliquid public Info API for user fills when a public wallet address is supplied.

The collector is intentionally light. It does not scan the entire chain, does not submit transactions, and does not need exchange credentials.

Important limitation: a Solana token-balance delta is a **candidate wallet activity signal**, not proof of a buy/sell. The next decoder layer must combine the delta with transaction instructions, quote-asset deltas and DEX program context before converting it into a TraderFill.

The public Solana RPC is shared/rate-limited infrastructure, so keep polling low-frequency.
