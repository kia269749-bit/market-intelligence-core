"""Central market-source guard for research inputs."""

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
