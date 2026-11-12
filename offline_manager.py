"""
TrendMatrix AI - Offline Data Manager

Loads previously cached NASA POWER observations or generates
clearly labelled synthetic demonstration data.

Cached NASA observations and synthetic demo data are kept separate.
Cached records are checked for source, variable, region, frequency,
and coordinates when coordinates are supplied.
"""

import json
import logging
import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from data_storage import (
    get_available_datasets,
    get_stored_dataset,
)


logger = logging.getLogger(__name__)


class OfflineDataError(Exception):
    """Raised when offline data cannot be prepared."""


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


# These settings are only for illustrative synthetic data.
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
        return dict(record)

    if hasattr(record, "keys"):
        return {key: record[key] for key in record.keys()}

    raise OfflineDataError(
        "The database returned an unsupported record format."
    )


def _normalise_text(value: Any) -> str:
    """Return normalized text for reliable metadata comparisons."""

    return str(value or "").strip().casefold()


def _coordinates_match(
    stored_value: Any,
    requested_value: Optional[float],
    tolerance: float = 0.0001,
) -> bool:
    """Compare stored and requested coordinates."""

    if requested_value is None:
        return True

    if stored_value is None:
        return False

    try:
        stored_number = float(stored_value)
        requested_number = float(requested_value)

        return (
            math.isfinite(stored_number)
            and math.isfinite(requested_number)
            and math.isclose(
                stored_number,
                requested_number,
                rel_tol=0,
                abs_tol=tolerance,
            )
        )
    except (TypeError, ValueError):
        return False


def _read_nested_metadata(dataset: dict) -> dict:
    """Decode the JSON metadata stored in the database."""

    raw_metadata = dataset.get("metadata_json")

    if not raw_metadata:
        return {}

    if isinstance(raw_metadata, dict):
        return raw_metadata

    try:
        decoded = json.loads(raw_metadata)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Could not decode cached dataset metadata.")
        return {}

    return decoded if isinstance(decoded, dict) else {}


def _is_real_nasa_dataset(dataset: dict) -> bool:
    """Reject synthetic and non-NASA database records."""

    if dataset.get("is_sample"):
        return False

    data_type = _normalise_text(dataset.get("data_type"))
    data_source = _normalise_text(dataset.get("data_source"))

    if data_type in {"sample", "sample_demo", "synthetic"}:
        return False

    return (
        data_type in {"live_nasa", "nasa"}
        or data_source == "nasa power"
    )


def get_cached_dataset(
    variable_id: str,
    region_name: Optional[str] = None,
    frequency: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Optional[dict]:
    """
    Retrieve the newest compatible cached NASA dataset.

    A dataset must match the requested variable and region.
    Frequency and coordinates are also checked when supplied.

    No fallback to another region is allowed.
    """

    datasets = get_available_datasets(
        variable_name=variable_id,
        region_name=region_name,
    )

    if not datasets:
        return None

    # The database normally returns newest-first records.
    # Sorting explicitly avoids relying on the database ordering.
    datasets = sorted(
        [_to_dict(record) for record in datasets],
        key=lambda item: str(item.get("fetched_at") or ""),
        reverse=True,
    )

    requested_region = _normalise_text(region_name)
    requested_frequency = _normalise_text(frequency)

    for dataset in datasets:

        if not _is_real_nasa_dataset(dataset):
            continue

        if _normalise_text(
            dataset.get("variable_name")
        ) != _normalise_text(variable_id):
            continue

        # Never use cached observations from a different region.
        if requested_region:
            cached_region = _normalise_text(
                dataset.get("region_name")
            )

            if cached_region != requested_region:
                continue

        # Never substitute daily data for monthly requests,
        # or monthly data for daily requests.
        if requested_frequency:
            cached_frequency = _normalise_text(
                dataset.get("frequency")
            )

            if cached_frequency != requested_frequency:
                continue

        # Coordinates must be supplied together.
        if (latitude is None) != (longitude is None):
            raise ValueError(
                "Latitude and longitude must be supplied together."
            )

        if latitude is not None and longitude is not None:

            if not _coordinates_match(
                dataset.get("latitude"),
                latitude,
            ):
                continue

            if not _coordinates_match(
                dataset.get("longitude"),
                longitude,
            ):
                continue

        dataset_id = dataset.get("id", dataset.get("dataset_id"))

        if dataset_id is None:
            continue

        stored = get_stored_dataset(int(dataset_id))

        if not stored:
            continue

        stored_dataset = _to_dict(stored["dataset"])

        if not _is_real_nasa_dataset(stored_dataset):
            continue

        observations = stored.get("observations")

        if not observations:
            continue

        observations_df = pd.DataFrame(
            [_to_dict(item) for item in observations]
        )

        date_column = (
            "observation_date"
            if "observation_date" in observations_df.columns
            else "date"
        )

        if (
            date_column not in observations_df.columns
            or "value" not in observations_df.columns
        ):
            continue

        observations_df[date_column] = pd.to_datetime(
            observations_df[date_column],
            errors="coerce",
        )

        observations_df["value"] = pd.to_numeric(
            observations_df["value"],
            errors="coerce",
        )

        observations_df = observations_df.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        observations_df = observations_df.dropna(
            subset=[date_column, "value"]
        )

        if observations_df.empty:
            continue

        observations_df = observations_df.sort_values(
            date_column
        )

        dataframe = observations_df.set_index(
            date_column
        )[["value"]].rename(
            columns={"value": variable_id}
        )

        # Merge database columns and decoded source metadata.
        metadata = dict(stored_dataset)
        nested_metadata = _read_nested_metadata(stored_dataset)

        metadata["source_metadata"] = nested_metadata

        metadata["spatial_type"] = nested_metadata.get(
            "spatial_type",
            "point",
        )

        metadata["region"] = stored_dataset.get("region_name")
        metadata["data_type"] = "cached_nasa"
        metadata["source_label"] = "Cached NASA POWER Data"
        metadata["is_sample"] = False

        dataframe.attrs.update(metadata)

        return {
            "success": True,
            "data": dataframe,
            "metadata": metadata,
            "data_type": "cached_nasa",
            "source_label": "Cached NASA POWER Data",
            "message": (
                "Previously downloaded NASA POWER observations "
                "loaded successfully."
            ),
        }

    return None


def generate_sample_dataset(
    variable_id: str,
    years: int = 10,
    frequency: str = "monthly",
    region_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> dict:
    """
    Generate synthetic demonstration data.

    These values are illustrative only. They are not NASA
    measurements and must not be treated as scientific evidence.
    """

    if variable_id not in SAMPLE_VARIABLE_SETTINGS:
        raise ValueError(
            f"Unsupported sample variable: {variable_id}"
        )

    if (
        isinstance(years, bool)
        or not isinstance(years, int)
        or not 1 <= years <= 100
    ):
        raise ValueError(
            "Years must be an integer between 1 and 100."
        )

    frequency = str(frequency).lower().strip()

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
        start_date = end_date - pd.DateOffset(years=years) + pd.Timedelta(days=1)

        dates = pd.date_range(
            start=start_date,
            end=end_date,
            freq="D",
        )

    settings = SAMPLE_VARIABLE_SETTINGS[variable_id]
    rng = np.random.default_rng(seed=42)

    time_index = np.arange(len(dates), dtype=float)

    trend = settings["trend"] * time_index

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
        "region": region_name,
        "region_name": region_name,
        "latitude": latitude,
        "longitude": longitude,
        "data_type": "sample_demo",
        "source_label": "Synthetic Demo Data",
        "is_sample": True,
        "spatial_type": "synthetic",
        "description": (
            "Synthetic demonstration data generated by "
            "TrendMatrix AI. These values are not actual "
            "NASA observations and are not scientific evidence."
        ),
    }

    dataframe.attrs.update(metadata)

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
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> dict:
    """
    Return compatible cached NASA data when available.

    If no compatible cache exists, generate labelled demo data.
    """

    if variable_id not in SAMPLE_VARIABLE_SETTINGS:
        raise ValueError(
            f"Unsupported variable: {variable_id}"
        )

    frequency = str(frequency).lower().strip()

    if frequency not in {"monthly", "daily"}:
        raise ValueError(
            "Frequency must be either 'monthly' or 'daily'."
        )

    try:
        cached_data = get_cached_dataset(
            variable_id=variable_id,
            region_name=region_name,
            frequency=frequency,
            latitude=latitude,
            longitude=longitude,
        )

        if cached_data is not None:
            return cached_data

        return generate_sample_dataset(
            variable_id=variable_id,
            years=years,
            frequency=frequency,
            region_name=region_name,
            latitude=latitude,
            longitude=longitude,
        )

    except (ValueError, OfflineDataError):
        raise

    except Exception as error:
        logger.exception(
            "Unable to prepare offline data: %s",
            error,
        )

        raise OfflineDataError(
            f"Unable to prepare offline data: {error}"
        ) from error


if __name__ == "__main__":

    print("TRENDMATRIX AI - OFFLINE DATA MANAGER")
    print("=" * 45)

    print("\n1. Testing cached NASA data retrieval...")

    cached_result = get_cached_dataset(
        variable_id="temperature",
    )

    if cached_result:
        print("Cached NASA data: Available")
        print("Observations:", len(cached_result["data"]))
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

    print("\nOffline data manager checks completed.")
