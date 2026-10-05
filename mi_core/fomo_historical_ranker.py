from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable

from .fomo_normalizer import FomoTraderSnapshot


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def historical_fomo_rank(
    snapshots: Iterable[FomoTraderSnapshot],
    min_snapshots: int = 3,
) -> list[dict]:
    grouped = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.trader_id:
            grouped[snapshot.trader_id].append(snapshot)

    ranked = []
    for trader_id, rows in grouped.items():
        rows = sorted(rows, key=lambda x: x.captured_at)
        if len(rows) < min_snapshots:
            continue

        ranks = [max(1, r.rank) for r in rows]
        pnls = [float(r.pnl_usd) for r in rows]
        volumes = [max(0.0, float(r.volume_usd)) for r in rows]
        trades = [max(0, int(r.trades)) for r in rows]

        avg_rank = mean(ranks)
        best_rank = min(ranks)
        rank_scale = max(1.0, max(ranks) - 1.0)
        rank_score = _clip01(1.0 - (avg_rank - 1.0) / rank_scale)

        pnl_positive = sum(x > 0 for x in pnls) / len(pnls)
        pnl_nonnegative = sum(x >= 0 for x in pnls) / len(pnls)

        if len(pnls) >= 2:
            first, last = pnls[0], pnls[-1]
            pnl_delta = last - first
            trend_scale = max(1.0, abs(first), abs(last))
            pnl_trend = max(-1.0, min(1.0, pnl_delta / trend_scale))
        else:
            pnl_trend = 0.0

        positive_pnl_score = _clip01(0.65 * pnl_positive + 0.35 * pnl_nonnegative)
        trend_score = _clip01(0.5 + 0.5 * pnl_trend)

        max_volume = max(volumes) if volumes else 0.0
        volume_presence = sum(x > 0 for x in volumes) / len(volumes)
        volume_score = _clip01(
            0.6 * volume_presence
            + 0.4 * (0.0 if max_volume <= 0 else mean(volumes) / max_volume)
        )

        activity_presence = sum(x > 0 for x in trades) / len(trades)
        max_trades = max(trades) if trades else 0
        activity_score = _clip01(
            0.6 * activity_presence
            + 0.4 * (0.0 if max_trades <= 0 else mean(trades) / max_trades)
        )

        sample_confidence = _clip01(len(rows) / 12.0)

        score = _clip01(
            0.30 * rank_score
            + 0.25 * positive_pnl_score
            + 0.15 * trend_score
            + 0.10 * volume_score
            + 0.10 * activity_score
            + 0.10 * sample_confidence
        )

        ranked.append({
            "trader_id": trader_id,
            "snapshots": len(rows),
            "avg_rank": round(avg_rank, 3),
            "best_rank": best_rank,
            "pnl_usd_latest": pnls[-1],
            "pnl_positive_rate": round(pnl_positive, 4),
            "pnl_trend": round(pnl_trend, 4),
            "avg_volume_usd": round(mean(volumes), 2),
            "avg_trades": round(mean(trades), 2),
            "sample_confidence": round(sample_confidence, 4),
            "historical_score": round(score, 6),
        })

    ranked.sort(
        key=lambda x: (x["historical_score"], x["pnl_usd_latest"], -x["avg_rank"]),
        reverse=True,
    )
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    return ranked
