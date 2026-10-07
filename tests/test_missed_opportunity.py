from mi_core.missed_opportunity import append_rejected, resolve, summarize
from pathlib import Path
import json


def _p60(path):
    rows=[]
    prices=[100.0,101.0,102.0,103.0,104.0,105.0,106.0]
    for i,p in enumerate(prices):
        rows.append({"timestamp":i,"coins":{"BTC":{"price":p}}})
    Path(path).write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")


def _snap():
    return {
        "capital_economics":{"approved":False,"tier":"REJECT","reason":"economic_floor_not_met","modeled_profit_usd":-1.0},
        "evidence":{
            "combined":{"actionable":False,"bias":"BEARISH","confidence":0.7,"agreement":0.8},
            "data_quality":{"status":"HEALTHY"},
            "forecast":{
                "available":True,"asset":"BTC","regime":"TREND",
                "selected":{"direction":"DOWN","expected_move_pct":0.8},
                "horizons":[{"horizon":5,"direction":"DOWN","expected_return_pct":-0.8}]
            }
        }
    }


def test_append_rejected_and_deduplicates(tmp_path):
    p60=tmp_path/"market.jsonl"; journal=tmp_path/"missed.jsonl"
    _p60(p60)
    assert append_rejected(str(journal),_snap(),str(p60))
    assert not append_rejected(str(journal),_snap(),str(p60))
    assert summarize(str(journal))["count"] == 1


def test_resolve_tracks_future_outcomes(tmp_path):
    p60=tmp_path/"market.jsonl"; journal=tmp_path/"missed.jsonl"
    _p60(p60)
    assert append_rejected(str(journal),_snap(),str(p60))
    # Entry at latest Project60 point cannot have future bars in this fixture,
    # so append a new observation after the entry timestamp.
    with p60.open("a",encoding="utf-8") as f:
        for i,p in enumerate([107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166],start=7):
            f.write(json.dumps({"timestamp":i,"coins":{"BTC":{"price":p}}})+"\n")
    assert resolve(str(journal),str(p60)) == 1
    s=summarize(str(journal))
    assert s["horizons"]["5"]["count"] == 1
    assert s["horizons"]["5"]["avg_directional_move_pct"] < 0
