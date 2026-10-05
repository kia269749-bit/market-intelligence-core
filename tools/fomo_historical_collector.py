from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'https://api.fomoapi.io'
OUT = Path('data/fomo/raw')

def get_json(path: str, timeout: int = 15) -> dict:
    key = os.environ.get('FOMO_API_KEY')
    if not key:
        raise RuntimeError('FOMO_API_KEY is not set; refusing unauthenticated data collection')
    req = Request(BASE + path, headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def append_jsonl(name: str, payload: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    record = {'captured_at': int(time.time()), 'payload': payload}
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
    return path

def collect_leaderboards() -> None:
    for window in ('24h', '7d', '30d', 'all'):
        payload = get_json(f'/v2/leaderboard/{window}?limit=100')
        append_jsonl(f'leaderboard_{window}.jsonl', payload)

def main() -> None:
    collect_leaderboards()
    print('FOMO HISTORICAL COLLECTOR: OK')

if __name__ == '__main__':
    main()