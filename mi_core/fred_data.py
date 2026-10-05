"""Low-load FRED economic-data adapter for research.

Credentials are read only from FRED_API_KEY in the environment. No key is stored
in the repository and this module never places orders.
"""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

@dataclass(frozen=True)
class EconomicObservation:
    series_id: str
    date: str
    value: float

def parse_observations(payload: dict, series_id: str) -> list[EconomicObservation]:
    rows = payload.get("observations")
    if not isinstance(rows, list):
        raise ValueError("FRED response has no observations list")
    out = []
    for row in rows:
        raw = row.get("value")
        day = row.get("date")
        if raw in (None, ".") or not day:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        out.append(EconomicObservation(series_id.upper(), day, value))
    return out

def fetch_series(series_id: str, api_key: str | None = None, observation_start: str | None = None,
                 observation_end: str | None = None, timeout: int = 20) -> list[EconomicObservation]:
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY is required; no credential is stored in the repository")
    params = {"series_id": series_id.upper(), "api_key": key, "file_type": "json",
              "sort_order": "asc"}
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    req = Request(BASE_URL + "?" + urlencode(params),
                  headers={"User-Agent": "market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return parse_observations(json.loads(response.read().decode("utf-8")), series_id)

def daily_returns(observations: list[EconomicObservation]) -> dict[str, float]:
    ordered = sorted(observations, key=lambda x: x.date)
    out = {}
    previous = None
    for obs in ordered:
        if previous is not None and previous > 0:
            out[obs.date] = obs.value / previous - 1.0
        previous = obs.value
    return out

def align_daily_series(series: dict[str, list[EconomicObservation]]) -> dict[str, dict[str, float]]:
    """Convert each series to date-keyed daily returns without forward-filling."""
    return {name.upper(): daily_returns(rows) for name, rows in series.items()}
