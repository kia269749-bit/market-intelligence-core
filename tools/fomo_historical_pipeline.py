from __future__ import annotations

import argparse
import json
from pathlib import Path

from mi_core.fomo_history_store import write_rankings
from mi_core.fomo_normalizer import FomoTraderSnapshot, dedupe_snapshots, normalize_leaderboard


def read_raw_file(path: Path) -> list[FomoTraderSnapshot]:
    window = path.stem.replace("leaderboard_", "")
    snapshots: list[FomoTraderSnapshot] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        snapshots.extend(
            normalize_leaderboard(
                record.get("payload", {}),
                window=window,
                captured_at=int(record.get("captured_at", 0)),
            )
        )
    return snapshots


def run(raw_dir: Path, normalized_path: Path, ranking_path: Path, min_snapshots: int) -> list[dict]:
    snapshots: list[FomoTraderSnapshot] = []
    for path in sorted(raw_dir.glob("leaderboard_*.jsonl")):
        snapshots.extend(read_raw_file(path))
    snapshots = dedupe_snapshots(snapshots)

    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_text(
        "".join(
            json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for row in snapshots
        ),
        encoding="utf-8",
    )
    return write_rankings(snapshots, ranking_path, min_snapshots=min_snapshots)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build historical FOMO rankings from collected raw snapshots.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/fomo/raw"))
    parser.add_argument("--normalized", type=Path, default=Path("data/fomo/normalized/snapshots.jsonl"))
    parser.add_argument("--rankings", type=Path, default=Path("data/fomo/reports/historical_ranking.jsonl"))
    parser.add_argument("--min-snapshots", type=int, default=3)
    args = parser.parse_args()
    ranked = run(args.raw_dir, args.normalized, args.rankings, args.min_snapshots)
    print(f"FOMO HISTORICAL PIPELINE: OK ({len(ranked)} ranked traders)")


if __name__ == "__main__":
    main()
