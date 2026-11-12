
"""
TrendMatrix AI - Data Storage Service

This module connects NASA POWER data retrieval, data processing,
and SQLite storage.

It provides functions to:
1. Fetch a variable from NASA POWER.
2. Clean and prepare the fetched observations.
3. Save dataset metadata and observations in SQLite.
4. Retrieve previously stored datasets.
"""

from typing import Any, Optional

import pandas as pd

from database import (
    init_db,
    save_dataset,
    save_observations,
    get_dataset,
    get_observations,
    list_datasets,
)

from nasa_power import fetch_variable_data

from data_processor import prepare_time_series


# NASA POWER currently supports these variables in our application.
NASA_POWER_VARIABLES = {
    "temperature",
    "humidity",
    "wind_speed",
    "precipitation",
    "solar_radiation",
}


class DataStorageError(Exception):
    """Raised when data retrieval, processing, or storage fails."""


def _validate_request(
    variable_id: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    region_name: str,
) -> None:
    """Validate the inputs before requesting external data."""

    if variable_id not in NASA_POWER_VARIABLES:
        raise ValueError(
            f"NASA POWER integration does not currently support "
            f"'{variable_id}'. Supported variables: "
            f"{', '.join(sorted(NASA_POWER_VARIABLES))}."
        )

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    if not region_name or not region_name.strip():
        raise ValueError("A region name is required.")

    start = pd.to_datetime(start_date, errors="raise")
    end = pd.to_datetime(end_date, errors="raise")

    if start > end:
        raise ValueError("Start date cannot be later than end date.")



def _build_observation_records(
    dataframe: pd.DataFrame,
    variable_id: str,
) -> list[dict[str, Any]]:
    """Convert a processed time series into database records."""

    if variable_id not in dataframe.columns:
        raise DataStorageError(
            f"Processed data does not contain '{variable_id}'."
        )

    records = []

    for observation_date, value in dataframe[variable_id].items():
        if pd.isna(value):
            continue

        records.append(
            {
                "date": pd.Timestamp(observation_date).strftime("%Y-%m-%d"),
                "value": float(value),
                "quality_flag": "valid",
            }
        )

    if not records:
        raise DataStorageError(
            "No valid observations are available to save."
        )

    return records


    records = []

    for observation_date, value in dataframe[variable_id].items():
        if pd.isna(value):
            continue

        records.append(
            {
                "observation_date": pd.Timestamp(
                    observation_date
                ).strftime("%Y-%m-%d"),
                "value": float(value),
                "quality_flag": "valid",
            }
        )

    if not records:
        raise DataStorageError(
            "No valid observations are available to save."
        )

    return records


def fetch_and_store_dataset(
    variable_id: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    region_name: str,
    frequency: str = "daily",
) -> dict[str, Any]:
    """
    Fetch NASA POWER observations, process them, and save them.

    Args:
        variable_id: TrendMatrix variable identifier.
        latitude: Geographic latitude.
        longitude: Geographic longitude.
        start_date: Beginning date in YYYY-MM-DD format.
        end_date: Ending date in YYYY-MM-DD format.
        region_name: Human-readable name of the selected region.
        frequency: Either 'daily' or 'monthly'.

    Returns:
        A dictionary containing the saved dataset ID and summary.
    """

    _validate_request(
        variable_id=variable_id,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        region_name=region_name,
    )

    frequency = frequency.lower().strip()

    if frequency not in {"daily", "monthly"}:
        raise ValueError(
            "Frequency must be either 'daily' or 'monthly'."
        )

    try:
        # Ensure the SQLite tables exist before saving data.
        init_db()

        # Step 1: Retrieve observations from NASA POWER.
        raw_data = fetch_variable_data(
            variable_id=variable_id,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )

        if raw_data.empty:
            raise DataStorageError(
                "NASA POWER returned no observations for this request."
            )

        # Preserve the source metadata before processing.
        source_metadata = dict(raw_data.attrs)

        # Step 2: Clean the observations and prepare the requested
        # daily or monthly time series.
        processed_data = prepare_time_series(
            raw_data,
            frequency=frequency,
            accumulation_variables=["precipitation"],
        )

        if processed_data.empty:
            raise DataStorageError(
                "No valid observations remained after processing."
            )

        # Step 3: Build the dataset metadata for SQLite.
        unit = source_metadata.get("units", {}).get(
            variable_id,
            "Unknown",
        )

        if frequency == "monthly" and variable_id == "precipitation":
            unit = "mm/month"

        dataset_metadata = {
            "variable_name": variable_id,
            "variable_code": variable_id,
            "data_source": "NASA POWER",
            "region_name": region_name.strip(),
            "start_date": processed_data.index.min().strftime(
                "%Y-%m-%d"
            ),
            "end_date": processed_data.index.max().strftime(
                "%Y-%m-%d"
            ),
            "frequency": frequency,
            "description": (
                f"{variable_id.replace('_', ' ').title()} observations "
                f"retrieved from NASA POWER."
            ),
            "unit": unit,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "data_type": "live_nasa",
            "is_sample": False,
            "metadata": {
                **source_metadata,
                "spatial_type": "point",
                "processing_frequency": frequency,
                "observation_count": len(processed_data),
                "note": (
                    "NASA POWER point data. This dataset represents "
                    "the requested coordinates, not a regional spatial "
                    "average."
                ),
            },
        }

        # Step 4: Save the dataset metadata and get its database ID.
        dataset_id = save_dataset(dataset_metadata)

        # Step 5: Convert processed values into observation records.
        observation_records = _build_observation_records(
            processed_data,
            variable_id,
        )

        # Step 6: Save the observations against the dataset ID.
        saved_count = save_observations(
            dataset_id,
            observation_records,
        )

        return {
            "success": True,
            "dataset_id": dataset_id,
            "variable": variable_id,
            "source": "NASA POWER",
            "data_type": "live_nasa",
            "region": region_name,
            "frequency": frequency,
            "unit": unit,
            "observations_saved": saved_count,
            "start_date": dataset_metadata["start_date"],
            "end_date": dataset_metadata["end_date"],
            "message": "Dataset fetched, processed, and saved successfully.",
        }

    except (ValueError, DataStorageError):
        raise

    except Exception as error:
        raise DataStorageError(
            f"Unable to fetch or store the dataset: {error}"
        ) from error


def get_stored_dataset(dataset_id: int) -> Optional[dict[str, Any]]:
    """Retrieve dataset metadata and its observations from SQLite."""

    init_db()

    dataset = get_dataset(dataset_id)

    if dataset is None:
        return None

    observations = get_observations(dataset_id)

    return {
        "dataset": dataset,
        "observations": observations,
    }


def get_available_datasets(
    variable_name: Optional[str] = None,
    region_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List saved datasets, optionally filtered by variable or region."""

    init_db()

    return list_datasets(
        variable_name=variable_name,
        region_name=region_name,
    )


if __name__ == "__main__":
    print("TRENDMATRIX AI - DATA STORAGE SERVICE")
    print("=" * 45)

    # Initialize the database without making an external API request.
    init_db()

    print("Database connection: Ready")
    print("NASA POWER integration: Available")
    print("Supported NASA POWER variables:")

    for variable in sorted(NASA_POWER_VARIABLES):
        print(f"- {variable}")

    print("\nExisting database datasets:")
    datasets = get_available_datasets()

    print(f"Total saved datasets: {len(datasets)}")
    print("\nData storage service initialized successfully.")
