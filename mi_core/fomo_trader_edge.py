from __future__ import annotations

from statistics import mean
from typing import Sequence


def build_trader_edge_matrix(
    replay_rows: Sequence[dict],
    *,
    min_events: int = 3,
) -> list[dict]:
    if min_events < 1:
        raise ValueError("min_events must be positive")

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in replay_rows:
        trader = str(row.get("trader_id", ""))
        symbol = str(row.get("symbol", ""))
        regime = str(row.get("regime", "UNKNOWN"))
        if not trader or not symbol:
            raise ValueError("replay rows require trader_id and symbol")
        groups.setdefault((trader, symbol, regime), []).append(row)

    matrix: list[dict] = []
    for (trader, symbol, regime), rows in groups.items():
        outcomes = [r["outcome"] for r in rows]
        n = len(outcomes)
        returns = [float(o.return_pct) for o in outcomes]
        positive = sum(r > 0 for r in returns) / n
        target = sum(bool(o.hit_target) for o in outcomes) / n
        stop = sum(bool(o.hit_stop) for o in outcomes) / n
        mean_up = mean(float(o.max_up_pct) for o in outcomes)
        mean_down = mean(float(o.max_down_pct) for o in outcomes)
        avg_conf = mean(float(r.get("trader_confidence", 0.0)) for r in rows)
        sample_confidence = min(1.0, n / 12.0)
        evidence_score = max(
            0.0,
            min(
                1.0,
                0.40 * positive
                + 0.20 * target
                + 0.15 * (1.0 - stop)
                + 0.15 * sample_confidence
                + 0.10 * max(0.0, min(1.0, avg_conf)),
            ),
        )
        matrix.append({
            "trader_id": trader,
            "symbol": symbol,
            "regime": regime,
            "events": n,
            "eligible": n >= min_events,
            "mean_return_pct": round(mean(returns), 6),
            "positive_return_rate": round(positive, 6),
            "target_hit_rate": round(target, 6),
            "stop_hit_rate": round(stop, 6),
            "mean_max_up_pct": round(mean_up, 6),
            "mean_max_down_pct": round(mean_down, 6),
            "avg_trader_confidence": round(avg_conf, 6),
            "sample_confidence": round(sample_confidence, 6),
            "evidence_score": round(evidence_score, 6),
        })

    return sorted(
        matrix,
        key=lambda x: (x["eligible"], x["evidence_score"], x["mean_return_pct"]),
        reverse=True,
    )
