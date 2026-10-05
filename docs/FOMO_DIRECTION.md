# FOMO Direction Engine

Research-only, read-only direction inference for Solana swaps.

Evidence sources can include target-token delta, quote-token delta, DEX event/instruction direction, pool/vault input-output direction, and CLMM base-input direction.

The engine combines independent witnesses and returns UNKNOWN when evidence is absent or materially conflicting. Confidence is a reliability score, not a probability of profit and never represents certainty.

Pipeline: Solana transaction -> DEX decoder -> pool/vault evidence -> token delta -> direction -> TraderFill.

No transaction signing, wallet control, order execution, or account mutation is performed.
