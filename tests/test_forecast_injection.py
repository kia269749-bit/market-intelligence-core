import inspect
import math
import unittest

from mi_core.validated_forecast import MarketBar, forecast_now


def make_bar(ts, price, index):
    signature = inspect.signature(MarketBar)
    values = {
        "ts": ts,
        "timestamp": ts,
        "symbol": "BTC",
        "asset": "BTC",
        "coin": "BTC",
        "price": price,
        "close": price,
        "volume": 100.0 + index,
        "buy_volume": 55.0,
        "sell_volume": 45.0,
        "buy": 55.0,
        "sell": 45.0,
        "oi": 10000.0 + index,
        "open_interest": 10000.0 + index,
        "funding": 0.0001,
        "bid_depth": 500000.0,
        "ask_depth": 450000.0,
        "bids": 500000.0,
        "asks": 450000.0,
    }

    kwargs = {}
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if name in values:
            kwargs[name] = values[name]
        elif param.default is inspect.Parameter.empty:
            raise AssertionError(
                f"Unknown required MarketBar field: {name}. "
                "Update make_bar() to supply a suitable value."
            )

    return MarketBar(**kwargs)


def make_bars(count=140):
    bars = []
    for i in range(count):
        # دادهٔ مصنوعی و قطعی، بدون نیاز به اینترنت یا کتابخانهٔ اضافی
        price = 60000.0 + i * 3.0 + (i % 7) * 2.0
        bars.append(make_bar(1_800_000_000 + i * 60, price, i))
    return bars


def assert_finite_forecast(test, result):
    if not isinstance(result, dict):
        test.fail(f"Unexpected result type: {type(result).__name__}")

    if result.get("available") is not True:
        return

    numeric_fields = (
        "p_up", "p_flat", "p_down", "expected_return_pct",
        "lower_return_pct", "upper_return_pct", "confidence",
        "breakout_probability", "current_move_pct",
    )
    for field in numeric_fields:
        value = result.get(field)
        test.assertIsInstance(value, (int, float), f"{field} is not numeric")
        test.assertTrue(math.isfinite(value), f"{field} is non-finite: {value}")


class ForecastInjectionTests(unittest.TestCase):
    def test_clean_input_is_processable(self):
        result = forecast_now(make_bars())
        self.assertIsInstance(result, dict)
        self.assertTrue(
            result.get("available"),
            f"Clean synthetic data unexpectedly rejected: {result}",
        )
        assert_finite_forecast(self, result)

    def test_nan_and_infinity_are_rejected(self):
        from dataclasses import replace

        for bad_value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad_value=bad_value):
                bars = make_bars()
                bars[-1] = replace(bars[-1], oi=bad_value)

                result = forecast_now(bars)
                self.assertIsInstance(result, dict)
                self.assertIs(
                    result.get("available"), False,
                    f"Invalid feature was not rejected: {result}",
                )
                self.assertEqual(result.get("reason"), "invalid_input")

    def test_reversed_timestamps_are_rejected(self):
        bars = make_bars()
        bars.reverse()

        result = forecast_now(bars)
        self.assertIsInstance(result, dict)
        self.assertIs(
            result.get("available"), False,
            f"Reversed timestamps were not rejected: {result}",
        )

    def test_duplicate_timestamps_are_rejected(self):
        bars = make_bars()
        duplicate = make_bar(bars[-2].ts, bars[-1].price, len(bars))
        bars[-1] = duplicate

        result = forecast_now(bars)
        self.assertIsInstance(result, dict)
        self.assertIs(
            result.get("available"), False,
            f"Duplicate timestamps were not rejected: {result}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
