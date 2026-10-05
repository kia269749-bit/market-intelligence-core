from .storage import append_jsonl

def record_signal(path, signal):
    append_jsonl(path, signal.to_dict())

def record_outcome(path, outcome):
    append_jsonl(path, outcome)
