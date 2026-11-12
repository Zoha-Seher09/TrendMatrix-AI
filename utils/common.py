"""
Common utility functions for TrendMatrix AI.

These helpers are shared across application services and routes.
"""

import inspect
import re

from datetime import date, datetime
from typing import Any

import pandas as pd


def to_dict(value: Any) -> dict:
    """Convert dictionary-like objects into regular dictionaries."""

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "keys"):
        return {key: value[key] for key in value.keys()}

    return {}


def safe_filename(value: str) -> str:
    """Convert arbitrary text into a filesystem-friendly filename."""

    return (
        re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value)).strip("_")
        or "output"
    )


def call_compatible(function, available_values: dict, aliases=None):
    """Pass only parameters supported by an existing project function."""

    signature = inspect.signature(function)
    aliases = aliases or {}

    kwargs = {}

    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )

    for name, parameter in signature.parameters.items():

        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        source_name = (
            name if name in available_values else aliases.get(name)
        )

        if source_name in available_values:
            kwargs[name] = available_values[source_name]

        elif parameter.default == inspect.Parameter.empty:
            raise RuntimeError(
                f"Missing required parameter '{name}' "
                f"for {function.__name__}."
            )

    if accepts_kwargs:
        for name, value in available_values.items():
            kwargs.setdefault(name, value)

    return function(**kwargs)


def json_safe(value: Any):
    """Convert Pandas and NumPy values into JSON-compatible values."""

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass

    return value
