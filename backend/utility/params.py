# backend/utils/params.py
from __future__ import annotations
from datetime import date, datetime
import pandas as pd
from typing import Any, Dict

DATE_KEYS_HINTS = ("date", "asof", "from", "to", "start", "end")

def _looks_like_date_key(key: str) -> bool:
    k = key.lower()
    return any(h in k for h in DATE_KEYS_HINTS)

def parse_dates_in_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with date-like values parsed to pandas.Timestamp."""
    out = {}
    for k, v in params.items():
        if v is None:
            out[k] = None
            continue

        if _looks_like_date_key(k):
            if isinstance(v, (datetime, date, pd.Timestamp)):
                out[k] = pd.Timestamp(v)
            elif isinstance(v, (int, float)):  # epoch seconds or ms? adjust if needed
                # If you store numeric dates, pick one convention and stick to it:
                out[k] = pd.to_datetime(v, unit="s", utc=True)  # or unit="ms"
            elif isinstance(v, str):
                out[k] = pd.to_datetime(v, errors="raise", utc=True)
            else:
                raise TypeError(f"Unsupported date type for '{k}': {type(v)}")
        else:
            out[k] = v
    return out

def ensure_numeric_params_only(params: Dict[str, Any]) -> Dict[str, float]:
    """Keep only numeric values; skip dates/strings to avoid float-cast errors."""
    numeric: Dict[str, float] = {}
    for k, v in params.items():
        if isinstance(v, (int, float)):
            numeric[k] = float(v)
        # skip non-numerics (dates, strings, etc.)
    return numeric
