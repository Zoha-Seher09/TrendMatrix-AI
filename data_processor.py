
"""
TrendMatrix AI - Data Processing Module

Cleans and prepares Earth science observations for analysis.

Features:
- Validates observation DataFrames.
- Converts values to numeric format.
- Handles invalid dates and missing values.
- Detects duplicate dates.
- Aggregates daily observations into monthly time series.
- Preserves source and location metadata.
- Generates data quality reports.

Scientific note:
Missing observations are not automatically interpolated.
Outliers are not automatically removed.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Processing configuration
# ---------------------------------------------------------------------

DEFAULT_ACCUMULATION_VARIABLES = ("precipitation",)


# ---------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------

def validate_dataframe(dataframe: pd.DataFrame) -> None:
    """Validate the basic structure of an observation DataFrame."""

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if dataframe.empty:
        raise ValueError("The observation DataFrame is empty.")

    if dataframe.columns.empty:
        raise ValueError("The DataFrame has no variables.")

    if not isinstance(dataframe.index, pd.DatetimeIndex):
        raise ValueError(
            "DataFrame index must be a pandas DatetimeIndex."
        )

    if dataframe.index.has_duplicates:
        raise ValueError(
            "Duplicate observation dates were found. "
            "Resolve duplicates before processing."
        )

    if not dataframe.index.is_monotonic_increasing:
        raise ValueError(
            "Observation dates must be sorted in ascending order."
        )


# ---------------------------------------------------------------------
# Data quality reporting
# ---------------------------------------------------------------------

def get_quality_report(dataframe: pd.DataFrame) -> dict:
    """
    Generate a data quality report.

    Reports missing values without modifying the observations.
    """

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    total_rows = len(dataframe)

    if total_rows == 0:
        return {
            "total_observations": 0,
            "missing_values": {},
            "missing_percentages": {},
            "complete_observations": 0,
        }

    missing_counts = dataframe.isna().sum()

    missing_percentages = (
        missing_counts / total_rows * 100
    ).round(2)

    return {
        "total_observations": total_rows,
        "missing_values": missing_counts.to_dict(),
        "missing_percentages": missing_percentages.to_dict(),
        "complete_observations": int(
            dataframe.notna().all(axis=1).sum()
        ),
    }


# ---------------------------------------------------------------------
# Data cleaning
# ---------------------------------------------------------------------

def clean_observations(
    dataframe: pd.DataFrame,
    drop_empty_rows: bool = True,
) -> pd.DataFrame:
    """
    Clean observations while preserving valid scientific information.

    Processing:
    1. Validate the input.
    2. Convert the index to datetime if necessary.
    3. Convert variable values to numeric.
    4. Replace infinite values with NaN.
    5. Optionally remove rows where every variable is missing.

    Missing values in partially complete rows are retained.
    """

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if dataframe.empty:
        raise ValueError("Cannot clean an empty DataFrame.")

    result = dataframe.copy()

    # Preserve source and dataset metadata.
    metadata = dict(dataframe.attrs)

    # Convert the index to datetime when required.
    if not isinstance(result.index, pd.DatetimeIndex):

        try:
            result.index = pd.to_datetime(
                result.index,
                errors="raise"
            )

        except (ValueError, TypeError) as error:
            raise ValueError(
                "Observation index contains invalid dates."
            ) from error

    if result.index.has_duplicates:
        raise ValueError(
            "Duplicate observation dates were found."
        )

    # Sort observations chronologically.
    result = result.sort_index()

    # Convert all observation columns to numeric values.
    for column in result.columns:

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce"
        )

        result[column] = result[column].replace(
            [np.inf, -np.inf],
            np.nan
        )

    # Remove only rows where all selected variables are missing.
    if drop_empty_rows:
        result = result.dropna(how="all")

    if result.empty:
        raise ValueError(
            "No valid observations remain after cleaning."
        )

    result.index.name = "date"

    # Restore metadata and attach a quality report.
    result.attrs = metadata
    result.attrs["quality_report"] = get_quality_report(result)

    return result


# ---------------------------------------------------------------------
# Monthly aggregation
# ---------------------------------------------------------------------

def aggregate_monthly(
    dataframe: pd.DataFrame,
    accumulation_variables=None,
) -> pd.DataFrame:
    """
    Aggregate daily observations into monthly observations.

    Aggregation rules:
    - Precipitation: sum daily values to calculate monthly totals.
    - Other variables: calculate monthly daily averages.

    Missing observations are not filled with invented values.
    """

    cleaned = clean_observations(dataframe)

    if accumulation_variables is None:
        accumulation_variables = DEFAULT_ACCUMULATION_VARIABLES

    accumulation_variables = set(accumulation_variables)

    monthly_columns = {}

    for column in cleaned.columns:

        if column in accumulation_variables:

            # Sum available daily accumulation values.
            monthly_columns[column] = (
                cleaned[column]
                .resample("MS")
                .sum(min_count=1)
            )

        else:

            # Calculate the average of available daily values.
            monthly_columns[column] = (
                cleaned[column]
                .resample("MS")
                .mean()
            )

    monthly_dataframe = pd.DataFrame(monthly_columns)

    monthly_dataframe.index.name = "date"

    # Remove months where all selected variables are missing.
    monthly_dataframe = monthly_dataframe.dropna(how="all")

    if monthly_dataframe.empty:
        raise ValueError(
            "Monthly aggregation produced no valid observations."
        )

    # Preserve the original dataset metadata.
    monthly_dataframe.attrs = dict(cleaned.attrs)

    monthly_dataframe.attrs["frequency"] = "monthly"
    monthly_dataframe.attrs["aggregation"] = {
        column: (
            "sum"
            if column in accumulation_variables
            else "mean"
        )
        for column in cleaned.columns
    }

    # Update precipitation units after monthly accumulation.
    units = dict(monthly_dataframe.attrs.get("units", {}))

    for column in accumulation_variables:

        if column in monthly_dataframe.columns:
            if units.get(column) == "mm/day":
                units[column] = "mm/month"

    if units:
        monthly_dataframe.attrs["units"] = units

    monthly_dataframe.attrs["quality_report"] = (
        get_quality_report(monthly_dataframe)
    )

    return monthly_dataframe


# ---------------------------------------------------------------------
# Main processing function
# ---------------------------------------------------------------------

def prepare_time_series(
    dataframe: pd.DataFrame,
    frequency: str = "daily",
    accumulation_variables=None,
) -> pd.DataFrame:
    """
    Prepare observations at the requested frequency.

    Supported frequencies:
    - daily
    - monthly
    """

    normalized_frequency = frequency.strip().lower()

    if normalized_frequency == "daily":

        result = clean_observations(dataframe)
        result.attrs["frequency"] = "daily"

        return result

    if normalized_frequency == "monthly":

        return aggregate_monthly(
            dataframe,
            accumulation_variables=accumulation_variables,
        )

    raise ValueError(
        "Unsupported frequency. Choose 'daily' or 'monthly'."
    )


# ---------------------------------------------------------------------
# Offline module test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    print("\nTRENDMATRIX AI - DATA PROCESSING TEST")
    print("=" * 55)

    # Create a small demonstration dataset.
    # This is synthetic test data, not NASA observations.

    sample_dates = pd.date_range(
        start="2020-01-01",
        periods=10,
        freq="D",
    )

    sample_dataframe = pd.DataFrame(
        {
            "temperature": [
                8.1, 9.3, 8.3, 10.2, 11.5,
                10.8, 9.7, 8.9, 9.2, 10.1,
            ],
            "humidity": [
                60.0, 55.0, 51.0, 50.0, 47.0,
                49.0, 53.0, 57.0, 56.0, 52.0,
            ],
            "precipitation": [
                0.0, 0.1, 0.0, 0.0, 0.2,
                0.0, 0.0, 0.3, 0.0, 0.0,
            ],
        },
        index=sample_dates,
    )

    sample_dataframe.index.name = "date"

    sample_dataframe.attrs["source"] = "Synthetic test data"
    sample_dataframe.attrs["data_type"] = "sample"
    sample_dataframe.attrs["units"] = {
        "temperature": "°C",
        "humidity": "%",
        "precipitation": "mm/day",
    }

    try:

        print("\n1. Testing daily data cleaning...")

        daily_data = prepare_time_series(
            sample_dataframe,
            frequency="daily",
        )

        print("Daily processing successful.")
        print(daily_data.head())

        print("\n2. Testing monthly aggregation...")

        monthly_data = prepare_time_series(
            daily_data,
            frequency="monthly",
        )

        print("Monthly aggregation successful.")
        print(monthly_data)

        print("\n3. Testing data quality report...")

        quality_report = get_quality_report(daily_data)

        print("Total observations:")
        print(quality_report["total_observations"])

        print("\nMissing values:")
        print(quality_report["missing_values"])

        print("\n4. Testing metadata preservation...")

        print("Source:", monthly_data.attrs["source"])
        print("Frequency:", monthly_data.attrs["frequency"])
        print("Units:", monthly_data.attrs["units"])

        print("\nData processing module tested successfully.")

    except (ValueError, TypeError) as error:

        print("\nData processing test failed.")
        print("Reason:", error)
