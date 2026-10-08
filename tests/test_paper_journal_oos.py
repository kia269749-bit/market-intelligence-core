from pathlib import Path
import json
from tools.paper_journal_oos import load_rows


def test_resolved_rows_become_oos_observations(tmp_path: Path):
    p=tmp_path/"journal.jsonl"
    p.write_text(
        json.dumps({"status":"TARGET","resolved_ts":2,"gross_move_pct":1.5,
                    "direction":"BULLISH","flow_score":0.7})+"\n"+
        json.dumps({"status":"OPEN","resolved_ts":3,"gross_move_pct":2,
                    "direction":"BEARISH","flow_score":-0.8})+"\n",
        encoding="utf-8",
    )
    rows=load_rows(p)
    assert len(rows)==1
    assert rows[0]["future_return_pct"]==1.5
    assert rows[0]["base_return_pct"]==1.0
    assert rows[0]["flow_score"]==0.7
