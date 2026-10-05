from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean, pstdev
from typing import Iterable, Sequence

@dataclass(frozen=True)
class TraderTrade:
    trader_id: str
    symbol: str
    entry_ts: int
    exit_ts: int | None
    entry_price: float
    exit_price: float | None
    qty: float
    pnl_usd: float
    invested_usd: float
    is_meme: bool = False
    early_entry: bool = False
    clean_exit: bool = False
    holding_minutes: float | None = None

    @property
    def roi(self) -> float:
        return self.pnl_usd / self.invested_usd if self.invested_usd > 0 else 0.0

    @property
    def size_usd(self) -> float:
        return max(0.0, self.invested_usd)

    def to_dict(self) -> dict:
        return asdict(self)

def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def _safe_mean(values: Sequence[float]) -> float:
    return mean(values) if values else 0.0

def max_drawdown(pnls: Iterable[float]) -> float:
    equity = peak = 0.0
    worst = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return _clip01(worst)

def consistency_score(rois: Sequence[float]) -> float:
    if not rois:
        return 0.0
    positive = sum(1 for r in rois if r > 0) / len(rois)
    if len(rois) < 2:
        stability = 1.0
    else:
        volatility = pstdev(rois)
        stability = 1.0 / (1.0 + min(5.0, volatility * 10.0))
    return _clip01(0.7 * positive + 0.3 * stability)

def trader_metrics(trades: Sequence[TraderTrade]) -> dict:
    if not trades:
        return {
            'trades': 0, 'pnl_usd': 0.0, 'roi': 0.0, 'win_rate': 0.0,
            'consistency': 0.0, 'drawdown': 0.0, 'avg_trade_size_usd': 0.0,
            'early_entry_rate': 0.0, 'clean_exit_rate': 0.0,
            'avg_holding_minutes': 0.0, 'meme_trades': 0, 'meme_pnl_usd': 0.0,
            'meme_roi': 0.0, 'meme_win_rate': 0.0,
        }
    pnls = [float(t.pnl_usd) for t in trades]
    rois = [t.roi for t in trades]
    invested = sum(max(0.0, t.invested_usd) for t in trades)
    wins = sum(1 for t in trades if t.pnl_usd > 0)
    meme = [t for t in trades if t.is_meme]
    meme_invested = sum(max(0.0, t.invested_usd) for t in meme)
    meme_wins = sum(1 for t in meme if t.pnl_usd > 0)
    durations = [t.holding_minutes for t in trades if t.holding_minutes is not None]
    return {
        'trades': len(trades), 'pnl_usd': sum(pnls),
        'roi': sum(pnls) / invested if invested > 0 else 0.0,
        'win_rate': wins / len(trades), 'consistency': consistency_score(rois),
        'drawdown': max_drawdown(pnls),
        'avg_trade_size_usd': _safe_mean([t.size_usd for t in trades]),
        'early_entry_rate': sum(1 for t in trades if t.early_entry) / len(trades),
        'clean_exit_rate': sum(1 for t in trades if t.clean_exit) / len(trades),
        'avg_holding_minutes': _safe_mean(durations), 'meme_trades': len(meme),
        'meme_pnl_usd': sum(t.pnl_usd for t in meme),
        'meme_roi': sum(t.pnl_usd for t in meme) / meme_invested if meme_invested > 0 else 0.0,
        'meme_win_rate': meme_wins / len(meme) if meme else 0.0,
    }

def elite_score(metrics: dict, min_trades: int = 20) -> float:
    trades = int(metrics.get('trades', 0))
    if trades < min_trades:
        return 0.0
    roi_component = _clip01(metrics.get('roi', 0.0) / 0.50)
    win_component = _clip01(metrics.get('win_rate', 0.0))
    consistency = _clip01(metrics.get('consistency', 0.0))
    drawdown_component = 1.0 - _clip01(metrics.get('drawdown', 0.0))
    timing = _clip01(0.6 * metrics.get('early_entry_rate', 0.0) + 0.4 * metrics.get('clean_exit_rate', 0.0))
    meme_component = _clip01(0.6 * (metrics.get('meme_roi', 0.0) / 0.50) + 0.4 * metrics.get('meme_win_rate', 0.0))
    raw = (0.25 * roi_component + 0.20 * win_component + 0.20 * consistency +
           0.15 * drawdown_component + 0.10 * timing + 0.10 * meme_component)
    sample_factor = min(1.0, trades / float(max(1, 2 * min_trades)))
    return round(_clip01(raw * sample_factor), 6)

def rank_traders(trader_trades: Iterable[TraderTrade], min_trades: int = 20) -> list[dict]:
    grouped: dict[str, list[TraderTrade]] = {}
    for trade in trader_trades:
        grouped.setdefault(trade.trader_id, []).append(trade)
    ranked = []
    for trader_id, trades in grouped.items():
        metrics = trader_metrics(trades)
        ranked.append({'trader_id': trader_id, 'elite_score': elite_score(metrics, min_trades=min_trades), **metrics})
    ranked.sort(key=lambda x: (x['elite_score'], x['pnl_usd']), reverse=True)
    for i, row in enumerate(ranked, 1):
        row['rank'] = i
    return ranked