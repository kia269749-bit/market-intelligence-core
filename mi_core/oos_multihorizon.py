"""Lightweight leakage-safe multi-horizon Project60 OOS validation."""
from .costs import get_round_trip_cost_pct
from .validated_forecast import forecast_acceptance_gate, score_capital_targets, score_predictions, walk_forward_forecast

DEFAULT_HORIZONS=(5,15,60,240)

def evaluate_project60_multihorizon(
    bars, horizons=DEFAULT_HORIZONS, train_window=300, capital_usd=500.0,
    min_profit_usd=4.0, preferred_profit_usd=10.0, cost_policy="base",
):
    round_trip_cost_pct = get_round_trip_cost_pct(cost_policy)
    out={"available":bool(bars),"bars":len(bars),"horizons":{},"cost_policy":cost_policy.strip().lower(),"round_trip_cost_pct":round_trip_cost_pct,"research_only":True,"live_orders":False}
    for horizon in horizons:
        h=int(horizon)
        window=min(int(train_window),max(60,len(bars)-h-1))
        result=walk_forward_forecast(bars,horizon=h,train_window=window,min_train=60)
        metrics=score_predictions(result)
        capital=score_capital_targets(result,capital_usd=capital_usd,min_profit_usd=min_profit_usd,preferred_profit_usd=preferred_profit_usd,cost_policy=cost_policy)
        gate=forecast_acceptance_gate(metrics,capital)
        out["horizons"][str(h)]={"train_window":window,"resolved":result.get("resolved",0),"accuracy":metrics.get("accuracy",0.0),"high_conf_samples":metrics.get("high_conf_samples",0),"high_conf_accuracy":metrics.get("high_conf_accuracy",0.0),"directional_samples":capital.get("resolved_directional",0),"usd4_hit_rate":capital.get("min_target_hit_rate",0.0),"usd10_hit_rate":capital.get("preferred_target_hit_rate",0.0),"required_move_pct":capital.get("min_required_move_pct",0.0),"preferred_required_move_pct":capital.get("preferred_required_move_pct",0.0),"acceptance":gate,"model_version":result.get("model_version")}
    return out
