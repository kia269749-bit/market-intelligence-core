"""Research-only: segmented, spaced walk-forward OOS check.
Samples are spaced, not statistically independent. No orders."""
import argparse, json, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mi_core.models import MarketBar
from mi_core.data_alignment import segment_and_deduplicate_bars
from mi_core.validated_forecast import walk_forward_forecast

MIN_FEATURE_INDEX = 20
MIN_TRAIN = 60


def minimum_segment_length(horizon, min_train=MIN_TRAIN):
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if isinstance(min_train, bool) or not isinstance(min_train, int) or min_train < 1:
        raise ValueError("min_train must be a positive integer")
    # First prediction needs enough past feature/label pairs and a full
    # future horizon: feature index + training rows + 2 * horizon + 1.
    return MIN_FEATURE_INDEX + min_train + 2 * horizon + 1

def num(v, d=0.0):
    try: return float(v)
    except (TypeError, ValueError): return d

def load(path):
    series = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                coins = row.get("coins", {})
                if isinstance(coins, list):
                    coins = {str(v.get("coin")): v for v in coins if isinstance(v, dict)}
                if not isinstance(coins, dict): continue
                ts = int(num(row.get("timestamp"), -1))
                if ts < 0: continue
                for s, a in coins.items():
                    if not isinstance(a, dict): continue
                    price = num(a.get("price"), float("nan"))
                    if not math.isfinite(price) or price <= 0: continue
                    tr, ob = a.get("trades") or {}, a.get("orderbook") or {}
                    series.setdefault(s, []).append(MarketBar(
                        ts=ts, symbol=s, price=price,
                        oi=num(a["open_interest"]) if a.get("open_interest") is not None else None,
                        funding=num(a["funding"]) if a.get("funding") is not None else None,
                        bid=num(ob.get("bid_usd")), ask=num(ob.get("ask_usd")),
                        buy_volume=num(tr.get("buy_usd")), sell_volume=num(tr.get("sell_usd"))))
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
    return series

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--symbols", default="BTC,ETH,SOL,XRP,DOGE")
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--gap", type=int, choices=(300, 600), default=600)
    ap.add_argument("--capital", type=float, default=500.0)
    ap.add_argument("--cost-pct", type=float, default=0.35)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.horizon < 1 or a.capital <= 0 or a.cost_pct < 0:
        ap.error("invalid horizon, capital, or cost")
    series = load(a.input)
    rng = random.Random(7)
    need = minimum_segment_length(a.horizon)
    report = {"horizon": a.horizon, "gap_s": a.gap, "min_segment_rows": need,
              "min_train": MIN_TRAIN, "min_feature_index": MIN_FEATURE_INDEX,
              "assets": {}, "research_only": True, "live_orders": False,
              "note": "spaced samples are not independent; assets are correlated"}
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        bars = series.get(sym, [])
        segs, alignment = segment_and_deduplicate_bars(bars, a.gap)
        aligned_rows = sum(len(seg) for seg in segs)
        longest_segment_rows = max((len(seg) for seg in segs), default=0)
        if longest_segment_rows < need:
            report["assets"][sym] = {
                "status": "no_segment_long_enough",
                "rows_before_alignment": alignment["raw_count"],
                "rows_after_alignment": aligned_rows,
                "duplicates_removed": alignment["duplicates_removed"],
                "min_segment_rows": need,
                "longest_segment_rows": longest_segment_rows,
                "segments_total": len(segs),
                "segments_skipped_short": len(segs),
                "alignment": alignment,
            }
            continue
        rows, eligible, used, skipped, no_predictions = [], 0, 0, 0, 0
        for seg in segs:
            if len(seg) < need:
                skipped += 1
                continue
            eligible += 1
            res = walk_forward_forecast(
                seg,
                horizon=a.horizon,
                train_window=min(300, max(MIN_TRAIN, len(seg) - a.horizon - 1)),
                min_train=MIN_TRAIN,
                fit_every=10,
            )
            last = -10**9
            segment_rows = []
            for p in res.get("predictions", []):
                idx = p.get("bar_index")
                actual = p.get("actual")
                ret = p.get("actual_return_pct")
                if not isinstance(idx, int) or actual not in (-1, 0, 1) or ret is None:
                    continue
                if idx - last < a.horizon:
                    continue
                segment_rows.append(p)
                last = idx
            if segment_rows:
                used += 1
                rows.extend(segment_rows)
            else:
                no_predictions += 1
        n = len(rows)
        if not n:
            report["assets"][sym] = {
                "status": "no_samples",
                "rows_before_alignment": alignment["raw_count"],
                "duplicates_removed": alignment["duplicates_removed"],
                "segments_total": len(segs),
                "segments_eligible": eligible,
                "segments_used": used,
                "segments_no_predictions": no_predictions,
                "segments_skipped_short": skipped,
                "alignment": alignment,
            }
            continue
        def net(r, direction):
            return a.capital * (float(r["actual_return_pct"]) * direction - a.cost_pct) / 100.0
        dirs = [r for r in rows if r.get("pred") in (-1, 1)]
        model_net = sum(net(r, r["pred"]) for r in dirs)
        rand_net = sum(net(r, rng.choice((-1, 1))) for r in dirs)
        seen, base_ok = {-1: 0, 0: 0, 1: 0}, 0
        for r in rows:
            guess = max(seen, key=seen.get) if sum(seen.values()) else 0
            base_ok += int(guess == r["actual"]); seen[r["actual"]] += 1
        report["assets"][sym] = {
            "rows_before_alignment": alignment["raw_count"],
            "duplicates_removed": alignment["duplicates_removed"],
            "segments_total": len(segs),
            "segments_eligible": eligible,
            "segments_used": used,
            "segments_no_predictions": no_predictions,
            "segments_skipped_short": skipped,
            "alignment": alignment,
            "spaced_samples": n,
            "directional_samples": len(dirs),
            "accuracy": round(sum(r["pred"] == r["actual"] for r in rows) / n, 4),
            "baseline_expanding_past_labels_acc": round(base_ok / n, 4),
            "baseline_always_flat_acc": round(sum(r["actual"] == 0 for r in rows) / n, 4),
            "model_net_usd_hypothetical": round(model_net, 2),
            "random_direction_net_usd_same_trades": round(rand_net, 2),
            "avg_net_per_trade_usd": round(model_net / len(dirs), 3) if dirs else None,
            "cost_pct_per_trade": a.cost_pct}
    out = json.dumps(report, indent=2, ensure_ascii=False)
    if a.out:
        parent = os.path.dirname(a.out)
        if parent: os.makedirs(parent, exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f: f.write(out + "\n")
        print("REPORT_WRITTEN", a.out)
    else: print(out)

if __name__ == "__main__":
    main()
