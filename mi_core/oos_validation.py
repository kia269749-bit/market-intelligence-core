"""Research-only chronological OOS evaluator built on walk-forward folds."""
from __future__ import annotations

from dataclasses import asdict
from typing import Callable, Sequence, TypeVar

from .walk_forward import walk_forward

T = TypeVar("T")


def evaluate_oos(
    items: Sequence[T],
    timestamps: Sequence[int],
    evaluator: Callable[[Sequence[T], Sequence[T]], dict],
    *,
    train_size: int,
    test_size: int,
    step: int | None = None,
    anchored: bool = False,
) -> dict:
    """Run an evaluator on chronological folds and aggregate test-only results."""
    folds = walk_forward(
        items,
        timestamps,
        train_size=train_size,
        test_size=test_size,
        step=step,
        anchored=anchored,
    )
    rows = []
    for train, test, fold in folds:
        train_result = evaluator(train, train)
        test_result = evaluator(train, test)
        rows.append({
            "fold": asdict(fold),
            "train_return": float(train_result.get("return", 0.0)),
            "oos_return": float(test_result.get("return", 0.0)),
            "oos_max_drawdown": float(test_result.get("max_drawdown", 0.0)),
            "oos_trades": int(test_result.get("trades_count", 0)),
        })
    oos = [row["oos_return"] for row in rows]
    return {
        "folds": rows,
        "fold_count": len(rows),
        "oos_return_mean": sum(oos) / len(oos) if oos else 0.0,
        "oos_positive_rate": sum(x > 0 for x in oos) / len(oos) if oos else 0.0,
        "oos_return_total": sum(oos),
        "research_only": True,
        "live_orders": False,
    }
