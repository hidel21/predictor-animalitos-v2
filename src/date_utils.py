from __future__ import annotations

from datetime import date, datetime
from typing import Union

DateLike = Union[date, datetime]


def to_date(value: DateLike) -> date:
    """Convierte un date/datetime a date.

    Streamlit puede devolver `datetime.date` y en algunos casos el código
    puede trabajar con `datetime.datetime`. Esta función normaliza.
    """

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"Expected date|datetime, got {type(value)!r}")


def clamp_date(value: DateLike, min_value: DateLike, max_value: DateLike) -> date:
    """Limita una fecha al rango inclusivo [min_value, max_value]."""

    v = to_date(value)
    mn = to_date(min_value)
    mx = to_date(max_value)

    if mn > mx:
        raise ValueError(f"Invalid date range: min_value ({mn}) > max_value ({mx})")

    if v < mn:
        return mn
    if v > mx:
        return mx
    return v
