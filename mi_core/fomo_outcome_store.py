from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping

def append_outcome(path: str | Path, outcome: Mapping[str, Any]) -> None:
    target=Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(outcome), ensure_ascii=False, sort_keys=True)+"\n")

def load_outcomes(path: str | Path) -> list[dict[str, Any]]:
    target=Path(path)
    if not target.exists():
        return []
    rows=[]
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line=line.strip()
            if line:
                value=json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows
