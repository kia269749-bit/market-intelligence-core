from .intelligence import score_bar
from .backtest import run
from .validation import metrics, monte_carlo, split_time, profitability_gate
from .central_config import load_settings


def make_signals(bars, threshold=.60):
    return [score_bar(b, bars[max(0, i-20):i], threshold) for i, b in enumerate(bars)]


def evaluate(bars, config=None):
    config = config or {}
    settings = load_settings()
    sig = make_signals(bars, config.get("entry_threshold", .60))
    result = run(
        bars, sig,
        initial=config.get("initial", 10000.0),
        fee_bps=config.get("fee_bps", settings.taker_fee_bps),
        slippage_bps=config.get("slippage_bps", settings.slippage_bps),
        latency_bars=config.get("latency_bars", settings.latency_bars),
        hold_bars=config.get("hold_bars", 1),
        risk_fraction=config.get("risk_fraction", .10),
    )
    m = metrics(result)
    pnls = [t.pnl / result["initial"] for t in result["trades"]]
    return {"metrics": m, "monte_carlo": monte_carlo(pnls),
            "profitability_gate": profitability_gate(m),
            "market_source": {"exchange": settings.exchange, "market": settings.market,
                              "product_group": settings.product_group,
                              "research_only": True, "live_orders": False}}


def train_test(bars, config=None):
    train, test = split_time(bars)
    return {"train": evaluate(train, config), "test": evaluate(test, config)}
