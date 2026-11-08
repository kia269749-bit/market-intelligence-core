#!/usr/bin/env python3
# Read-only Project60 diagnostic anatomy.
# Does not modify model, data, configuration, or services.

import sys
import math
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mi_core.validated_forecast import (
    walk_forward_forecast,
    _feature_cache,
    _labels_cache,
    _training_indices,
    _fit,
    _predict,
)

from tools.project60_edge_evaluation import (
    load_bars,
    non_overlapping_predictions,
)

INPUT = ROOT / "data/real_oos_audit/BTCUSDT_1h_1000.jsonl"

HORIZON = 5
MIN_TRAIN = 60
FLAT_BAND = 0.0015
FIT_EVERY = 1

CLASSES = (-1, 0, 1)

FEATURES = [
    "momentum_5",
    "momentum_10",
    "momentum_20",
    "flow_5",
    "flow_20",
    "open_interest_change",
    "funding",
    "volatility_20",
]

GROUPS = {
    "Momentum": [0, 1, 2],
    "Order Flow": [3, 4],
    "Open Interest": [5],
    "Funding": [6],
    "Volatility": [7],
}

def section(title):
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)

def pct(value):
    return f"{value * 100:.2f}%"

def mean(values):
    return sum(values) / len(values) if values else 0.0

def capture_walk_forward_weights(bars, official_result, train_window):
    feature_cache = _feature_cache(bars)
    label_cache = _labels_cache(bars, HORIZON, FLAT_BAND)

    model = None
    next_fit_i = None
    replay = {}
    weights_by_index = {}

    for i in range(max(20, MIN_TRAIN), len(bars) - HORIZON):
        X = []
        y = []

        for j in _training_indices(i, HORIZON, train_window):
            f = feature_cache[j]
            lab = label_cache[j]
            if f is not None and lab is not None:
                X.append(f)
                y.append(lab)

        if len(X) < MIN_TRAIN:
            continue

        if model is None or next_fit_i is None or i >= next_fit_i:
            model = _fit(X, y)
            next_fit_i = i + FIT_EVERY

        x = feature_cache[i]
        if x is None:
            continue

        probabilities = _predict(model, x)
        pred = max(probabilities, key=probabilities.get)
        actual = label_cache[i]

        replay[i] = {
            "pred": pred,
            "actual": actual,
            "p_down": probabilities[-1],
            "p_flat": probabilities[0],
            "p_up": probabilities[1],
        }

        weights_by_index[i] = [list(class_weights) for class_weights in model[2]]

    official = {
        int(row["bar_index"]): row
        for row in official_result.get("predictions", [])
    }

    mismatches = []
    tolerance = 1e-5
    probability_fields = ("p_down", "p_flat", "p_up")

    for index, row in official.items():
        replayed = replay.get(index)
        if replayed is None:
            mismatches.append((index, "missing replay"))
            continue

        if replayed["pred"] != row["pred"]:
            mismatches.append((
                index,
                f"prediction mismatch: replay={replayed['pred']} official={row['pred']}"
            ))

        if replayed["actual"] != row["actual"]:
            mismatches.append((
                index,
                f"actual mismatch: replay={replayed['actual']} official={row['actual']}"
            ))

        for field in probability_fields:
            if field not in row:
                mismatches.append((index, f"official probability missing: {field}"))
                continue

            difference = abs(float(replayed[field]) - float(row[field]))
            if difference > tolerance:
                mismatches.append((
                    index,
                    f"{field} mismatch: replay={replayed[field]:.8f} "
                    f"official={float(row[field]):.8f} diff={difference:.8g}"
                ))

    extra = set(replay) - set(official)
    if extra:
        mismatches.append(("extra predictions", sorted(extra)[:10]))

    if mismatches:
        section("FATAL: WALK-FORWARD REPLAY MISMATCH")
        for item in mismatches[:20]:
            print(item)
        raise RuntimeError("Replay did not match official predictions/probabilities.")

    print(
        f"Replay verification: PASS | Official: {len(official)} | "
        f"Replayed: {len(replay)} | Probability tolerance: {tolerance}"
    )
    return weights_by_index

def print_confusion_matrix(rows):
    section("TABLE 1: 3x3 CONFUSION MATRIX")
    matrix = {actual: {pred: 0 for pred in CLASSES} for actual in CLASSES}
    actual_counts = Counter()
    predicted_counts = Counter()

    for row in rows:
        actual = row["actual"]
        pred = row["pred"]
        matrix[actual][pred] += 1
        actual_counts[actual] += 1
        predicted_counts[pred] += 1

    print("Rows = Actual | Columns = Predicted")
    print("Each cell shows: count (percentage within actual class)\n")
    print(f"{'Actual':>10}{'Pred -1':>18}{'Pred 0':>18}{'Pred +1':>18}{'Recall':>12}")

    for actual in CLASSES:
        total = actual_counts[actual]
        cells = []
        for pred in CLASSES:
            count = matrix[actual][pred]
            share = count / total if total else 0.0
            cells.append(f"{count} ({pct(share)})")
        recall = matrix[actual][actual] / total if total else 0.0
        print(f"{actual:>10}{cells[0]:>18}{cells[1]:>18}{cells[2]:>18}{pct(recall):>12}")

    total = len(rows)
    correct = sum(matrix[c][c] for c in CLASSES)
    accuracy = correct / total if total else 0.0

    print("\nClass statistics:")
    for c in CLASSES:
        support = actual_counts[c]
        predicted = predicted_counts[c]
        recall = matrix[c][c] / support if support else 0.0
        precision = matrix[c][c] / predicted if predicted else 0.0
        print(f"Class {c:+d}: actual={support:3d} | predicted={predicted:3d} | recall={pct(recall)} | precision={pct(precision)}")

    print(f"\nTotal independent samples: {total}")
    print(f"Correct predictions: {correct}")
    print(f"Overall accuracy: {pct(accuracy)}")
    return matrix, accuracy

def print_signal_inversion(rows):
    section("TABLE 2: SIGNAL INVERSION TEST")
    total = len(rows)
    original_correct = 0
    inverted_correct = 0
    directional_count = 0
    flat_count = 0

    actual_counts = Counter(row["actual"] for row in rows)
    majority_class, majority_count = actual_counts.most_common(1)[0] if actual_counts else (None, 0)
    baseline = majority_count / total if total else 0.0

    for row in rows:
        actual = row["actual"]
        pred = row["pred"]
        original_correct += int(pred == actual)
        if pred == 1:
            inverted = -1
            directional_count += 1
        elif pred == -1:
            inverted = 1
            directional_count += 1
        else:
            inverted = 0
            flat_count += 1
        inverted_correct += int(inverted == actual)

    original_accuracy = original_correct / total if total else 0.0
    inverted_accuracy = inverted_correct / total if total else 0.0
    original_edge = (original_accuracy - baseline) * 100
    inverted_edge = (inverted_accuracy - baseline) * 100

    print(f"Independent samples: {total}")
    print(f"Directional predictions inverted: {directional_count}")
    print(f"FLAT predictions unchanged: {flat_count}")
    print(f"Majority class: {majority_class}")
    print(f"Majority baseline: {pct(baseline)}")
    print()
    print(f"Original accuracy: {pct(original_accuracy)}")
    print(f"Original edge vs baseline: {original_edge:+.2f} pp")
    print()
    print(f"Inverted accuracy: {pct(inverted_accuracy)}")
    print(f"Inverted edge vs baseline: {inverted_edge:+.2f} pp")
    print()
    if inverted_edge > 0:
        print("INVERSION RESULT: Positive edge against majority baseline.")
    elif inverted_edge < 0:
        print("INVERSION RESULT: Still below majority baseline.")
    else:
        print("INVERSION RESULT: Equal to majority baseline.")

def print_weight_analysis(rows, weights_by_index):
    section("TABLE 3: WALK-FORWARD CLASS-CONTRAST WEIGHTS")

    selected_weights = []
    for row in rows:
        index = int(row["bar_index"])
        if index not in weights_by_index:
            raise RuntimeError(f"Missing captured W matrix for bar index {index}")
        W_check = weights_by_index[index]
        try:
            if len(W_check) != 3:
                raise ValueError(f"{len(W_check)} class rows, expected 3")
            for k, class_row in enumerate(W_check):
                if len(class_row) != len(FEATURES):
                    raise ValueError(
                        f"class row {k} has {len(class_row)} columns, "
                        f"expected {len(FEATURES)}"
                    )
                for v in class_row:
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        raise ValueError(f"class row {k} has non-numeric value {v!r}")
                    if not math.isfinite(v):
                        raise ValueError(f"class row {k} has non-finite value {v!r}")
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid captured W matrix for bar index {index}: {exc}"
            ) from exc
        selected_weights.append(weights_by_index[index])

    if not selected_weights:
        raise RuntimeError("No independent prediction weights available.")

    print(f"Weight matrices used: {len(selected_weights)}")
    print("Class order: DOWN=-1, FLAT=0, UP=+1")
    print("Weights are based on per-window Z-score standardized features.")
    print("Contrasts describe conditional log-odds coefficients, not causal effects.")
    print()

    header = (
        f"{'Feature':<25}{'UP-DOWN':>14}{'UP-FLAT':>14}"
        f"{'DOWN-FLAT':>14}{'Centered |W|':>16}"
    )
    print(header)
    print("-" * len(header))

    direction_strength = []

    for j, name in enumerate(FEATURES):
        up_down = [W[2][j] - W[0][j] for W in selected_weights]
        up_flat = [W[2][j] - W[1][j] for W in selected_weights]
        down_flat = [W[0][j] - W[1][j] for W in selected_weights]

        centered_abs = []
        for W in selected_weights:
            class_mean = mean([W[0][j], W[1][j], W[2][j]])
            centered_abs.extend(abs(W[k][j] - class_mean) for k in range(3))

        strength = mean([abs(value) for value in up_down])
        direction_strength.append(strength)

        print(
            f"{name:<25}{mean(up_down):>14.6f}"
            f"{mean(up_flat):>14.6f}{mean(down_flat):>14.6f}"
            f"{mean(centered_abs):>16.6f}"
        )

    print("\nFeature group comparison by mean |UP-DOWN|:")
    print(f"{'Group':<22}{'Features':>10}{'Mean strength':>18}{'Sum strength':>16}")
    print("-" * 66)

    group_results = []
    for group, indices in GROUPS.items():
        values = [direction_strength[i] for i in indices]
        group_mean = mean(values)
        group_sum = sum(values)
        group_results.append((group, group_mean, group_sum))
        print(f"{group:<22}{len(indices):>10}{group_mean:>18.6f}{group_sum:>16.6f}")

    ranked = sorted(group_results, key=lambda item: item[1], reverse=True)
    print("\nRanking by average absolute UP-DOWN contrast:")
    for rank, (group, group_mean, _) in enumerate(ranked, 1):
        print(f"{rank}. {group}: {group_mean:.6f}")

def main():
    section("PROJECT60 DIAGNOSTIC ANATOMY")
    print(f"Repository: {ROOT}")
    print(f"Input: {INPUT}")
    print(f"Horizon: {HORIZON}")
    print("Mode: READ ONLY | Live orders: DISABLED")

    if not INPUT.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT}")

    bars, audit = load_bars(INPUT, "BTC")
    print(f"Valid bars: {audit['valid_bars']}")

    train_window = min(300, max(60, len(bars) - HORIZON - 1))
    print(f"Train window: {train_window}")

    official = walk_forward_forecast(
        bars,
        horizon=HORIZON,
        train_window=train_window,
        min_train=MIN_TRAIN,
        flat_band=FLAT_BAND,
        fit_every=FIT_EVERY,
    )

    if not official.get("available"):
        raise RuntimeError(f"Forecast unavailable: {official.get('reason')}")

    independent = non_overlapping_predictions(official, bars, HORIZON)
    independent = [row for row in independent if row.get("actual") in CLASSES and row.get("pred") in CLASSES]

    section("SAMPLE VALIDATION")
    print(f"All official predictions: {len(official['predictions'])}")
    print(f"Independent resolved samples: {len(independent)}")

    weights_by_index = capture_walk_forward_weights(bars, official, train_window)
    print_confusion_matrix(independent)
    print_signal_inversion(independent)
    print_weight_analysis(independent, weights_by_index)

    section("FINAL INTEGRITY STATUS")
    print("Diagnostic completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nDIAGNOSTIC FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
