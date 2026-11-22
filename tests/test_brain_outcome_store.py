import json
from mi_core.brains.outcome_store import OutcomeStore

def test_append_only_outcome_counts_resolved_wins_and_losses(tmp_path):
    store = OutcomeStore(tmp_path / "outcomes.jsonl")
    base = {"signal_id": "s1", "brain_id": "technical.rsi", "family": "technical", "symbol": "BTC", "direction": "LONG", "resolved": True, "won": True}
    store.append(base)
    store.append({**base, "signal_id": "s2", "won": False})
    assert store.performance("technical.rsi") == {"wins": 1, "losses": 1}
    assert len((tmp_path / "outcomes.jsonl").read_text().splitlines()) == 2

def test_unresolved_is_not_counted(tmp_path):
    store = OutcomeStore(tmp_path / "outcomes.jsonl")
    row = {"signal_id": "s1", "brain_id": "flow", "family": "orderflow", "symbol": "BTC", "direction": "SHORT", "resolved": False, "won": None}
    store.append(row)
    assert store.performance("flow") == {"wins": 0, "losses": 0}
