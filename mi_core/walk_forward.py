"""Chronological train/test and walk-forward validation primitives.

Research-only: no network, credentials, or order execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, TypeVar
T = TypeVar("T")

@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_size: int
    test_size: int

def _validate_timestamps(timestamps: Sequence[int]) -> None:
    if not timestamps:
        raise ValueError("timestamps must not be empty")
    if any(timestamps[i] >= timestamps[i + 1] for i in range(len(timestamps) - 1)):
        raise ValueError("timestamps must be strictly increasing with no duplicates")

def chronological_split(items: Sequence[T], timestamps: Sequence[int], *, train_size: int, test_size: int):
    if len(items) != len(timestamps):
        raise ValueError("items and timestamps must have equal length")
    _validate_timestamps(timestamps)
    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be positive")
    if train_size + test_size > len(items):
        raise ValueError("train_size + test_size exceeds available observations")
    train_end = train_size
    test_end = train_end + test_size
    fold = WalkForwardFold(0, 0, train_end, train_end, test_end, train_size, test_size)
    return list(items[:train_end]), list(items[train_end:test_end]), fold

def walk_forward(items: Sequence[T], timestamps: Sequence[int], *, train_size: int, test_size: int, step: int | None = None, anchored: bool = False):
    if len(items) != len(timestamps):
        raise ValueError("items and timestamps must have equal length")
    _validate_timestamps(timestamps)
    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step is None else step
    if step < 1:
        raise ValueError("step must be positive")
    if train_size + test_size > len(items):
        return []
    folds = []
    test_start = train_size
    index = 0
    while test_start + test_size <= len(items):
        train_start = 0 if anchored else test_start - train_size
        train_end = test_start
        test_end = test_start + test_size
        fold = WalkForwardFold(index, train_start, train_end, test_start, test_end, train_end-train_start, test_end-test_start)
        folds.append((list(items[train_start:train_end]), list(items[test_start:test_end]), fold))
        index += 1
        test_start += step
    return folds
