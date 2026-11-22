"""Performance-weighted specialist consensus. No execution capability is provided."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from .contracts import BrainProposal, BrainResult, MarketSnapshot
ROUND_TRIP_COST_PCT = 0.12
PRIOR_WIN_RATE = 0.50
PRIOR_STRENGTH = 10.0
MIN_RESOLVED_FOR_FULL_WEIGHT = 20

def _performance_weight(stats: Mapping | None):
    stats = stats or {}
    wins, losses = max(0, int(stats.get("wins", 0))), max(0, int(stats.get("losses", 0)))
    n = wins + losses
    posterior = (wins + PRIOR_WIN_RATE * PRIOR_STRENGTH) / (n + PRIOR_STRENGTH)
    reliability = n / (n + MIN_RESOLVED_FOR_FULL_WEIGHT)
    # Neutral history must not halve every new specialist's confidence.
    # Performance changes relative weight only after resolved samples exist.
    weight = max(0.50, min(1.50, 1.0 + (posterior - 0.5) * reliability * 2))
    return weight, (wins / n if n else None), n

def arbitrate(snapshot: MarketSnapshot, proposals: Iterable[BrainProposal], performance: Mapping[str, Mapping] | None = None, min_independent_families: int = 2, min_confidence: float = 0.55, max_age_ms: int = 120_000) -> BrainResult:
    """Use win rate as a sample-shrunk weight; require independent specialist families."""
    performance = performance or {}
    valid = []
    for p in proposals:
        if not p.available or p.direction == "NO_TRADE": continue
        if p.as_of_ms > snapshot.as_of_ms or snapshot.as_of_ms - p.as_of_ms > max_age_ms: continue
        if p.direction not in ("LONG", "SHORT") or p.confidence < min_confidence: continue
        # If a strategy supplies a complete payoff estimate, require positive
        # expected return after the locked 0.12% round-trip cost. Do not invent
        # payoff values when the strategy has not supplied them.
        if p.expected_win_rate is not None and p.expected_win_pct is not None and p.expected_loss_pct is not None:
            try:
                win_rate = float(p.expected_win_rate)
                win_pct = float(p.expected_win_pct)
                loss_pct = float(p.expected_loss_pct)
            except (TypeError, ValueError):
                continue
            if (not all(map(__import__("math").isfinite, (win_rate, win_pct, loss_pct)))
                    or not 0.0 <= win_rate <= 1.0 or win_pct < 0.0 or loss_pct < 0.0):
                continue
            net_expectancy_pct = win_rate * win_pct - (1.0 - win_rate) * loss_pct - ROUND_TRIP_COST_PCT
            if net_expectancy_pct <= 0.0:
                continue
        weight, wr, n = _performance_weight(performance.get(p.brain_id))
        valid.append((p, weight, wr, n))
    family_best = {}
    for item in valid:
        p, weight, wr, n = item
        score = weight * p.confidence
        key = (p.family, p.direction)
        if key not in family_best or score > family_best[key][0]: family_best[key] = (score, item)
    totals, family_sets = {"LONG": 0.0, "SHORT": 0.0}, {"LONG": set(), "SHORT": set()}
    weighted_wins, win_weights, vote_rows = {"LONG": 0.0, "SHORT": 0.0}, {"LONG": 0.0, "SHORT": 0.0}, []
    for (family, direction), (score, item) in family_best.items():
        p, weight, wr, n = item
        totals[direction] += score; family_sets[direction].add(family)
        if wr is not None: weighted_wins[direction] += wr * score; win_weights[direction] += score
        vote_rows.append({"brain_id": p.brain_id, "family": family, "direction": direction, "confidence": p.confidence, "performance_weight": round(weight, 4), "historical_win_rate": wr, "resolved": n, "score": round(score, 4)})
    winner = "LONG" if totals["LONG"] > totals["SHORT"] else "SHORT" if totals["SHORT"] > totals["LONG"] else "NO_TRADE"
    families, total = family_sets.get(winner, set()), totals.get(winner, 0.0)
    other = totals["SHORT" if winner == "LONG" else "LONG"] if winner != "NO_TRADE" else 0.0
    agreement = total / max(total + other, 1e-12) if winner != "NO_TRADE" else 0.0
    winning_scores = [score for (family, direction), (score, _item) in family_best.items()
                      if direction == winner] if winner != "NO_TRADE" else []
    mean_strength = sum(winning_scores) / len(winning_scores) if winning_scores else 0.0
    confidence = agreement * mean_strength
    if winner == "NO_TRADE": reasons = ("no_directional_consensus",)
    elif len(families) < min_independent_families: winner, confidence, reasons = "NO_TRADE", 0.0, ("insufficient_independent_brain_families",)
    elif confidence < min_confidence: winner, confidence, reasons = "NO_TRADE", 0.0, ("weighted_consensus_below_threshold",)
    else: reasons = ("independent_specialist_consensus", "win_rate_shrunk_by_sample_size")
    wr = (weighted_wins[winner] / win_weights[winner]) if winner != "NO_TRADE" and win_weights[winner] else None
    return BrainResult(winner, snapshot.symbol, snapshot.as_of_ms, round(confidence, 4), tuple(sorted(families)) if winner != "NO_TRADE" else (), round(wr, 4) if wr is not None else None, reasons, tuple(vote_rows), True, False)
