"""
TrendMatrix AI - Data Processing Module

Cleans and prepares Earth science observations for analysis.

Features:
- Validates observation DataFrames.
- Converts values to numeric format.
- Handles invalid dates and missing values.
- Detects duplicate dates.
- Aggregates daily observations into monthly time series.
- Tracks monthly observation coverage.
- Preserves source and location metadata.
- Generates data quality reports.

Scientific note:
Missing observations are not automatically interpolated.
Outliers are not automatically removed.
Incomplete monthly coverage is reported explicitly.
"""

import numpy as np
import pandas as pd


DEFAULT_ACCUMULATION_VARIABLES = ("precipitation",)


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
        raise ValueError("Duplicate observation dates were found.")

    if not dataframe.index.is_monotonic_increasing:
        raise ValueError(
            "Observation dates must be sorted in ascending order."
        )


def get_quality_report(dataframe: pd.DataFrame) -> dict:
    """Generate a report of missing and complete observations."""

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


def clean_observations(
    dataframe: pd.DataFrame,
    drop_empty_rows: bool = True,
) -> pd.DataFrame:
    """
    Clean observations without inventing missing scientific values.

    Converts dates and numeric values, replaces infinite values
    with NaN, sorts dates, and optionally removes completely
    empty rows.
    """

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if dataframe.empty:
        raise ValueError("Cannot clean an empty DataFrame.")

    if dataframe.columns.empty:
        raise ValueError("The DataFrame has no variables.")

    result = dataframe.copy()
    metadata = dict(dataframe.attrs)

    if not isinstance(result.index, pd.DatetimeIndex):
        try:
            result.index = pd.to_datetime(
                result.index,
                errors="raise",
            )
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Observation index contains invalid dates."
            ) from error

    if result.index.has_duplicates:
        raise ValueError("Duplicate observation dates were found.")

    result = result.sort_index()

    for column in result.columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        result[column] = result[column].replace(
            [np.inf, -np.inf],
            np.nan,
        )

    if drop_empty_rows:
        result = result.dropna(how="all")

    if result.empty:
        raise ValueError(
            "No valid observations remain after cleaning."
        )

    result.index.name = "date"

    result.attrs = metadata
    result.attrs["quality_report"] = get_quality_report(result)

    return result


def aggregate_monthly(
    dataframe: pd.DataFrame,
    accumulation_variables=None,
) -> pd.DataFrame:
    """
    Aggregate daily observations into monthly observations.

    Accumulation variables:
        Sum available daily values.

    Other variables:
        Calculate the average of available daily values.

    Monthly coverage is recorded separately for every variable.
    Missing days are never filled with invented observations.
    """

    cleaned = clean_observations(dataframe)

    if accumulation_variables is None:
        accumulation_variables = DEFAULT_ACCUMULATION_VARIABLES

    if isinstance(accumulation_variables, str):
        accumulation_variables = [accumulation_variables]

    accumulation_variables = set(accumulation_variables)

    monthly_columns = {}
    monthly_coverage = {}

    for column in cleaned.columns:

        grouped = cleaned[column].resample("MS")

        if column in accumulation_variables:
            monthly_values = grouped.sum(min_count=1)
            aggregation_method = "sum"
        else:
            monthly_values = grouped.mean()
            aggregation_method = "mean"

        monthly_columns[column] = monthly_values

        valid_counts = grouped.count()

        coverage_records = []

        for month, valid_days in valid_counts.items():
            expected_days = int(month.days_in_month)

            coverage_records.append({
                "month": month.strftime("%Y-%m"),
                "valid_observations": int(valid_days),
                "expected_calendar_days": expected_days,
                "coverage_percent": round(
                    (int(valid_days) / expected_days) * 100,
                    2,
                ),
            })

        monthly_coverage[column] = {
            "aggregation": aggregation_method,
            "months": coverage_records,
        }

    monthly_dataframe = pd.DataFrame(monthly_columns)

    monthly_dataframe.index.name = "date"

    monthly_dataframe = monthly_dataframe.dropna(how="all")

    if monthly_dataframe.empty:
        raise ValueError(
            "Monthly aggregation produced no valid observations."
        )

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

    monthly_dataframe.attrs["monthly_coverage"] = monthly_coverage

    units = dict(monthly_dataframe.attrs.get("units", {}))

    for column in accumulation_variables:
        if column in monthly_dataframe.columns:
            if units.get(column) == "mm/day":
                units[column] = "mm (monthly accumulation; check coverage)"

    if units:
        monthly_dataframe.attrs["units"] = units

    monthly_dataframe.attrs["quality_report"] = (
        get_quality_report(monthly_dataframe)
    )

    return monthly_dataframe


def prepare_time_series(
    dataframe: pd.DataFrame,
    frequency: str = "daily",
    accumulation_variables=None,
) -> pd.DataFrame:
    """
    Prepare observations at the requested frequency.

    Supported frequencies: daily and monthly.
    """

    if not isinstance(frequency, str):
        raise TypeError("Frequency must be a string.")

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


if __name__ == "__main__":

    print("\nTRENDMATRIX AI - DATA PROCESSING TEST")
    print("=" * 55)

    # Synthetic data for testing only, not NASA observations.
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
        print("\n1. Testing daily processing...")

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

        print("\n3. Testing quality report...")

        quality_report = get_quality_report(daily_data)

        print(quality_report)

        print("\n4. Testing monthly coverage...")

        print(
            monthly_data.attrs["monthly_coverage"]
        )

        print("\n5. Testing metadata preservation...")

        print("Source:", monthly_data.attrs["source"])
        print("Frequency:", monthly_data.attrs["frequency"])
        print("Units:", monthly_data.attrs["units"])

        print("\nData processing module tested successfully.")

    except (ValueError, TypeError) as error:
        print("\nData processing test failed.")
        print("Reason:", error)
        raise

