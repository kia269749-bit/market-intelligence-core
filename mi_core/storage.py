import json
from pathlib import Path
from .models import MarketBar

def append_jsonl(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n")

def read_jsonl(path):
    p = Path(path)
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

def load_bars(path):
    return [MarketBar(**x) for x in read_jsonl(path)]
