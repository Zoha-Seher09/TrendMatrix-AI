
"""
TrendMatrix AI - Offline Data Manager

This module provides access to previously cached NASA observations
and generates clearly labelled synthetic demo data when no cached
dataset is available.

Important:
- Cached NASA data is previously downloaded real NASA data.
- Sample/demo data is synthetic and is never presented as NASA data.
- This module does not require an internet connection.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd

from data_storage import (
    get_available_datasets,
    get_stored_dataset,
)


class OfflineDataError(Exception):
    """Raised when offline data cannot be prepared."""


# Default units used when generating synthetic demonstration data.
VARIABLE_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "wind_speed": "m/s",
    "precipitation": "mm/month",
    "soil_moisture": "kg/m²",
    "evapotranspiration": "mm/month",
    "ndvi": "index",
    "solar_radiation": "kWh/m²/day",
}

# Approximate starting values and trends for illustrative demo data.
# These values are synthetic and are not scientific observations.
SAMPLE_VARIABLE_SETTINGS = {
    "temperature": {"base": 18.0, "trend": 0.025, "season": 8.0},
    "humidity": {"base": 60.0, "trend": -0.03, "season": 10.0},
    "wind_speed": {"base": 3.5, "trend": 0.002, "season": 0.8},
    "precipitation": {"base": 45.0, "trend": 0.05, "season": 20.0},
    "soil_moisture": {"base": 180.0, "trend": -0.15, "season": 25.0},
    "evapotranspiration": {"base": 55.0, "trend": 0.08, "season": 15.0},
    "ndvi": {"base": 0.45, "trend": 0.0005, "season": 0.15},
    "solar_radiation": {"base": 15.0, "trend": 0.01, "season": 4.0},
}


def _to_dict(record: Any) -> dict:
    """Convert SQLite rows or dictionary-like records to dictionaries."""

    if isinstance(record, dict):
        return record

    if hasattr(record, "keys"):
        return {key: record[key] for key in record.keys()}

    raise OfflineDataError(
        "The database returned an unsupported record format."
    )


def _get_dataset_variable(dataset: dict) -> Optional[str]:
    """Read the variable identifier from dataset metadata."""

    return (
        dataset.get("variable_name")
        or dataset.get("variable_code")
        or dataset.get("variable")
    )


def get_cached_dataset(
    variable_id: str,
    region_name: Optional[str] = None,
) -> Optional[dict]:
    """
    Retrieve a previously saved NASA dataset.

    Returns None when no matching cached NASA dataset is found.
    """

    datasets = get_available_datasets(
        variable_name=variable_id,
        region_name=region_name,
    )

    # If no region-specific match exists, try any cached region
    # for the requested variable.
    if not datasets and region_name:
        datasets = get_available_datasets(
            variable_name=variable_id
        )

    if not datasets:
        return None

    # Prefer real NASA datasets rather than sample/demo records.
    for record in reversed(datasets):
        dataset = _to_dict(record)

        is_sample = dataset.get("is_sample", False)
        data_type = dataset.get("data_type", "")

        if is_sample or data_type in {"sample_demo", "sample"}:
            continue

        dataset_id = dataset.get("id", dataset.get("dataset_id"))

        if dataset_id is None:
            continue

        stored = get_stored_dataset(int(dataset_id))

        if not stored:
            continue

        metadata = _to_dict(stored["dataset"])
        observations = stored["observations"]

        if not observations:
            continue

        rows = [_to_dict(item) for item in observations]
        observations_df = pd.DataFrame(rows)

        date_column = (
            "date" if "date" in observations_df.columns
            else "observation_date"
        )

        if date_column not in observations_df.columns:
            continue

        if "value" not in observations_df.columns:
            continue

        observations_df[date_column] = pd.to_datetime(
            observations_df[date_column],
            errors="coerce",
        )

        observations_df["value"] = pd.to_numeric(
            observations_df["value"],
            errors="coerce",
        )

        observations_df = observations_df.dropna(
            subset=[date_column, "value"]
        )

        if observations_df.empty:
            continue

        observations_df = observations_df.sort_values(date_column)

        dataframe = observations_df.set_index(date_column)[
            ["value"]
        ].rename(columns={"value": variable_id})

        metadata["data_type"] = "cached_nasa"
        metadata["source_label"] = "Cached NASA Data"
        metadata["is_sample"] = False

        return {
            "success": True,
            "data": dataframe,
            "metadata": metadata,
            "data_type": "cached_nasa",
            "source_label": "Cached NASA Data",
            "message": "Previously downloaded NASA observations loaded successfully.",
        }

    return None


def generate_sample_dataset(
    variable_id: str,
    years: int = 10,
    frequency: str = "monthly",
) -> dict:
    """
    Generate synthetic time-series data for demonstration purposes.

    The generated values are illustrative only and must never be
    interpreted as actual NASA measurements.
    """

    if variable_id not in SAMPLE_VARIABLE_SETTINGS:
        raise ValueError(
            f"Unsupported sample variable: {variable_id}"
        )

    if years < 1 or years > 100:
        raise ValueError("Years must be between 1 and 100.")

    frequency = frequency.lower().strip()

    if frequency not in {"monthly", "daily"}:
        raise ValueError(
            "Frequency must be either 'monthly' or 'daily'."
        )

    end_date = pd.Timestamp.today().normalize()

    if frequency == "monthly":
        dates = pd.date_range(
            end=end_date.to_period("M").to_timestamp(),
            periods=years * 12,
            freq="MS",
        )
    else:
        dates = pd.date_range(
            end=end_date,
            periods=years * 365,
            freq="D",
        )

    settings = SAMPLE_VARIABLE_SETTINGS[variable_id]
    rng = np.random.default_rng(seed=42)

    time_index = np.arange(len(dates), dtype=float)

    # Apply a small illustrative trend over the generated time period.
    trend = settings["trend"] * time_index

    # Generate a repeating seasonal pattern.
    seasonal_period = 12 if frequency == "monthly" else 365
    seasonal = settings["season"] * np.sin(
        2 * np.pi * time_index / seasonal_period
    )

    noise_scale = max(
        abs(settings["base"]) * 0.05,
        0.01,
    )

    noise = rng.normal(
        loc=0,
        scale=noise_scale,
        size=len(dates),
    )

    values = settings["base"] + trend + seasonal + noise

    # Apply reasonable display bounds to selected variables.
    if variable_id == "humidity":
        values = np.clip(values, 0, 100)

    elif variable_id == "ndvi":
        values = np.clip(values, -1, 1)

    elif variable_id in {
        "wind_speed",
        "precipitation",
        "soil_moisture",
        "evapotranspiration",
        "solar_radiation",
    }:
        values = np.maximum(values, 0)

    dataframe = pd.DataFrame(
        {variable_id: values},
        index=dates,
    )

    dataframe.index.name = "date"

    metadata = {
        "variable_name": variable_id,
        "unit": VARIABLE_UNITS[variable_id],
        "frequency": frequency,
        "data_type": "sample_demo",
        "source_label": "Synthetic Demo Data",
        "is_sample": True,
        "description": (
            "Synthetic demonstration data generated by TrendMatrix AI. "
            "These values are not actual NASA observations."
        ),
    }

    return {
        "success": True,
        "data": dataframe,
        "metadata": metadata,
        "data_type": "sample_demo",
        "source_label": "Synthetic Demo Data",
        "message": (
            "Synthetic demonstration data generated successfully. "
            "This is not real NASA data."
        ),
    }


def get_offline_dataset(
    variable_id: str,
    region_name: Optional[str] = None,
    years: int = 10,
    frequency: str = "monthly",
) -> dict:
    """
    Return cached NASA observations when available.

    If no cached observations exist, return clearly labelled
    synthetic demonstration data.
    """

    if variable_id not in SAMPLE_VARIABLE_SETTINGS:
        raise ValueError(
            f"Unsupported variable: {variable_id}"
        )

    try:
        cached_data = get_cached_dataset(
            variable_id=variable_id,
            region_name=region_name,
        )

        if cached_data is not None:
            return cached_data

        return generate_sample_dataset(
            variable_id=variable_id,
            years=years,
            frequency=frequency,
        )

    except (ValueError, OfflineDataError):
        raise

    except Exception as error:
        raise OfflineDataError(
            f"Unable to prepare offline data: {error}"
        ) from error


if __name__ == "__main__":
    print("TRENDMATRIX AI - OFFLINE DATA MANAGER")
    print("=" * 45)

    print("\n1. Testing cached NASA data retrieval...")

    cached_result = get_cached_dataset(
        variable_id="temperature"
    )

    if cached_result:
        print("Cached NASA data: Available")
        print(
            "Observations:",
            len(cached_result["data"]),
        )
        print("Source:", cached_result["source_label"])
    else:
        print("Cached NASA data: Not available")

    print("\n2. Testing synthetic demo data...")

    sample_result = generate_sample_dataset(
        variable_id="temperature",
        years=2,
        frequency="monthly",
    )

    print("Sample data: Generated")
    print("Source:", sample_result["source_label"])
    print("Observations:", len(sample_result["data"]))
    print("Unit:", sample_result["metadata"]["unit"])

    print("\n3. Testing automatic offline selection...")

    result = get_offline_dataset(
        variable_id="temperature",
        years=2,
        frequency="monthly",
    )

    print("Selected source:", result["source_label"])
    print("Data type:", result["data_type"])
    print("Observations:", len(result["data"]))

    print("\nOffline data manager tested successfully.")
