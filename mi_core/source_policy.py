"""Central source guards for market observations and cost assumptions."""


def is_lbank_futures_record(record):
    """Return true only for records explicitly tagged as LBank Futures data."""
    if not isinstance(record, dict):
        return False
    source = str(
        record.get("source")
        or record.get("exchange")
        or record.get("primary_exchange")
        or ""
    ).strip().lower()
    market = str(record.get("market") or record.get("market_type") or "").strip().lower()
    product_group = record.get("product_group") or record.get("productGroup")
    if not source.startswith("lbank") or market != "futures":
        return False
    if product_group is not None and str(product_group) != "SwapU":
        return False
    return True


def is_project60_perpetual_record(record):
    """Accept explicitly identified Hyperliquid perps or LBank Futures snapshots.

    Hyperliquid's Project60 collector historically identifies the source as
    'hyperliquid'; an omitted market field is accepted for that exact source
    because the collector is configured against Hyperliquid's perp info API.
    Explicit spot/other-market labels are rejected.
    """
    if not isinstance(record, dict):
        return False
    source = str(
        record.get("source")
        or record.get("exchange")
        or record.get("primary_exchange")
        or ""
    ).strip().lower()
    market = str(record.get("market") or record.get("market_type") or "").strip().lower()
    if source.startswith("lbank"):
        return is_lbank_futures_record(record)
    if source not in ("hyperliquid", "hyperliquid_perps", "hyperliquid_perpetuals"):
        return False
    return market in ("", "perp", "perps", "perpetual", "perpetuals", "futures", "swap")
