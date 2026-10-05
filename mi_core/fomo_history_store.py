from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from mi_core.fomo_historical_ranker import historical_fomo_rank
from mi_core.fomo_normalizer import FomoTraderSnapshot


def write_rankings(
    snapshots: Iterable[FomoTraderSnapshot],
    output_path: str | Path,
    *,
    min_snapshots: int = 3,
) -> list[dict]:
    rows = historical_fomo_rank(snapshots, min_snapshots=min_snapshots)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return rows


def load_snapshots(path: str | Path) -> list[FomoTraderSnapshot]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        rows.append(FomoTraderSnapshot(**data))
    return rows
