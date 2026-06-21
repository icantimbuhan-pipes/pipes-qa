from datetime import datetime
from typing import Optional

_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
)


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    for fmt in _FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def avg_per_minute(total: int, first_ts: Optional[str], last_ts: Optional[str]) -> Optional[float]:
    """Return average messages per minute over the span [first_ts, last_ts]."""
    if not first_ts or not last_ts or total == 0:
        return None
    t0, t1 = _parse_dt(first_ts), _parse_dt(last_ts)
    if t0 is None or t1 is None:
        return None
    minutes = (t1 - t0).total_seconds() / 60
    if minutes < 0.01:
        return None
    return total / minutes


def rate_pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 2)
