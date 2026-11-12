
"""
TrendMatrix AI - NASA POWER Data Service

Fetches daily point-based meteorological and solar observations
from the official NASA POWER API.

Important:
- Retrieves point data, not a regional spatial average.
- Uses NASA response metadata for units when available.
- Uses a verified parameter-unit mapping as a fallback.
- Converts NASA's missing-value marker (-999) to NaN.
- GLDAS and MODIS variables require separate data services.
"""

from datetime import datetime
from typing import Iterable

import pandas as pd
import requests

from config import NASA_POWER_BASE_URL, NASA_REQUEST_TIMEOUT


# ---------------------------------------------------------------------
# NASA POWER configuration
# ---------------------------------------------------------------------

NASA_POWER_DAILY_ENDPOINT = (
    f"{NASA_POWER_BASE_URL.rstrip('/')}/daily/point"
)

NASA_POWER_COMMUNITY = "RE"

POWER_VARIABLES = {
    "temperature": "T2M",
    "humidity": "RH2M",
    "wind_speed": "WS10M",
    "precipitation": "PRECTOTCORR",
    "solar_radiation": "ALLSKY_SFC_SW_DWN",
}

# Verified fallback units for the selected NASA POWER parameters.
# The API response metadata takes priority when it provides units.
POWER_UNITS = {
    "T2M": "°C",
    "RH2M": "%",
    "WS10M": "m/s",
    "PRECTOTCORR": "mm/day",
    "ALLSKY_SFC_SW_DWN": "kWh/m²/day",
}

DEFAULT_VARIABLES = list(POWER_VARIABLES.keys())
MISSING_VALUE = -999


class NASAAPIError(Exception):
    """Raised when NASA POWER returns an invalid or unsuccessful response."""


# ---------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------

def _validate_coordinates(latitude: float, longitude: float) -> None:
    """Validate geographic coordinates."""

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")


def _format_date(date_value) -> str:
    """Convert a date into NASA POWER's YYYYMMDD format."""

    if isinstance(date_value, (datetime, pd.Timestamp)):
        return date_value.strftime("%Y%m%d")

    date_text = str(date_value).strip()

    for date_format in ("%Y-%m-%d", "%Y%m%d"):
        try:
            parsed_date = datetime.strptime(date_text, date_format)
            return parsed_date.strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"Invalid date: {date_value}. "
        "Use YYYY-MM-DD or YYYYMMDD."
    )


def _validate_date_range(start_date, end_date) -> tuple:
    """Validate and format the requested date range."""

    formatted_start = _format_date(start_date)
    formatted_end = _format_date(end_date)

    if formatted_start > formatted_end:
        raise ValueError("Start date cannot be after end date.")

    return formatted_start, formatted_end


def _resolve_variables(variable_ids: Iterable[str]) -> dict:
    """Convert TrendMatrix variable IDs into NASA POWER parameter codes."""

    if isinstance(variable_ids, str):
        variable_ids = [variable_ids]
    else:
        variable_ids = list(variable_ids)

    if not variable_ids:
        raise ValueError("Select at least one variable.")

    selected_parameters = {}

    for variable_id in variable_ids:

        if variable_id not in POWER_VARIABLES:
            supported = ", ".join(POWER_VARIABLES.keys())

            raise ValueError(
                f"'{variable_id}' is not supported by NASA POWER "
                f"in this module. Supported variables: {supported}"
            )

        selected_parameters[variable_id] = POWER_VARIABLES[variable_id]

    return selected_parameters


# ---------------------------------------------------------------------
# NASA POWER response processing
# ---------------------------------------------------------------------

def _extract_parameter_units(response_data: dict) -> dict:
    """
    Extract units from NASA POWER response metadata.

    Handles dictionary and list metadata structures.
    """

    units = {}

    header = response_data.get("header", {})

    if not isinstance(header, dict):
        return units

    parameter_information = header.get("parameter_information", [])

    if isinstance(parameter_information, dict):

        for parameter_code, details in parameter_information.items():

            if isinstance(details, dict):
                unit = details.get("units")

                if unit:
                    units[parameter_code] = unit

    elif isinstance(parameter_information, list):

        for item in parameter_information:

            if not isinstance(item, dict):
                continue

            parameter_code = item.get("parameter")
            unit = item.get("units")

            if parameter_code and unit:
                units[parameter_code] = unit

    return units


def _get_parameter_units(
    parameter_code: str,
    api_units: dict
) -> str:
    """
    Return API-provided units or use the verified fallback mapping.
    """

    api_unit = api_units.get(parameter_code)

    if api_unit:
        return api_unit

    return POWER_UNITS.get(parameter_code, "Unknown")


def _process_response(
    response_data: dict,
    selected_variables: dict,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Convert the NASA POWER JSON response into a clean DataFrame."""

    try:
        parameter_data = response_data["properties"]["parameter"]

    except (KeyError, TypeError):
        raise NASAAPIError(
            "NASA POWER response does not contain the expected "
            "parameter data."
        )

    if not isinstance(parameter_data, dict):
        raise NASAAPIError("Invalid NASA POWER parameter data format.")

    api_units = _extract_parameter_units(response_data)

    dataframe_columns = {}

    for variable_id, parameter_code in selected_variables.items():

        if parameter_code not in parameter_data:
            raise NASAAPIError(
                f"NASA POWER did not return parameter: {parameter_code}"
            )

        observations = parameter_data[parameter_code]

        if not isinstance(observations, dict):
            raise NASAAPIError(
                f"Invalid observation format for {parameter_code}."
            )

        series = pd.Series(observations, name=variable_id)

        series.index = pd.to_datetime(
            series.index,
            format="%Y%m%d",
            errors="coerce"
        )

        series = pd.to_numeric(series, errors="coerce")

        # Replace NASA's missing-value marker.
        series = series.replace(MISSING_VALUE, float("nan"))

        # Remove invalid dates.
        series = series[~series.index.isna()]

        dataframe_columns[variable_id] = series

    dataframe = pd.DataFrame(dataframe_columns)

    dataframe.index.name = "date"
    dataframe = dataframe.sort_index()

    # Remove dates where all selected parameters are missing.
    dataframe = dataframe.dropna(how="all")

    if dataframe.empty:
        raise NASAAPIError(
            "NASA POWER returned no valid observations "
            "for the selected location and dates."
        )

    # Attach metadata for downstream processing.
    dataframe.attrs["source"] = "NASA POWER"
    dataframe.attrs["data_type"] = "live_nasa"
    dataframe.attrs["spatial_type"] = "point"
    dataframe.attrs["latitude"] = latitude
    dataframe.attrs["longitude"] = longitude
    dataframe.attrs["start_date"] = start_date
    dataframe.attrs["end_date"] = end_date
    dataframe.attrs["frequency"] = "daily"
    dataframe.attrs["community"] = NASA_POWER_COMMUNITY

    dataframe.attrs["units"] = {
        variable_id: _get_parameter_units(
            parameter_code,
            api_units
        )
        for variable_id, parameter_code in selected_variables.items()
    }

    return dataframe


# ---------------------------------------------------------------------
# Main NASA POWER API function
# ---------------------------------------------------------------------

def fetch_daily_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variable_ids=None,
    community: str = NASA_POWER_COMMUNITY,
) -> pd.DataFrame:
    """
    Fetch daily NASA POWER observations for one geographic point.

    Args:
        latitude: Geographic latitude (-90 to 90).
        longitude: Geographic longitude (-180 to 180).
        start_date: Starting date (YYYY-MM-DD or YYYYMMDD).
        end_date: Ending date (YYYY-MM-DD or YYYYMMDD).
        variable_ids: List of TrendMatrix variable IDs.
        community: NASA POWER user community.

    Returns:
        pandas.DataFrame:
            Daily observations indexed by date.
    """

    _validate_coordinates(latitude, longitude)

    formatted_start, formatted_end = _validate_date_range(
        start_date,
        end_date
    )

    if variable_ids is None:
        variable_ids = DEFAULT_VARIABLES

    selected_variables = _resolve_variables(variable_ids)

    parameter_codes = ",".join(selected_variables.values())

    request_parameters = {
        "parameters": parameter_codes,
        "community": community,
        "longitude": longitude,
        "latitude": latitude,
        "start": formatted_start,
        "end": formatted_end,
        "format": "JSON",
        "time-standard": "UTC",
    }

    try:
        response = requests.get(
            NASA_POWER_DAILY_ENDPOINT,
            params=request_parameters,
            timeout=NASA_REQUEST_TIMEOUT,
        )

        response.raise_for_status()

    except requests.exceptions.Timeout as error:
        raise NASAAPIError(
            "NASA POWER request timed out. Please try again."
        ) from error

    except requests.exceptions.HTTPError as error:

        try:
            error_details = response.json()
        except ValueError:
            error_details = response.text[:500]

        raise NASAAPIError(
            f"NASA POWER HTTP error {response.status_code}: "
            f"{error_details}"
        ) from error

    except requests.exceptions.RequestException as error:
        raise NASAAPIError(
            f"Could not connect to NASA POWER: {error}"
        ) from error

    try:
        response_data = response.json()

    except ValueError as error:
        raise NASAAPIError(
            "NASA POWER returned an invalid JSON response."
        ) from error

    if not isinstance(response_data, dict):
        raise NASAAPIError("Unexpected NASA POWER response format.")

    messages = response_data.get("messages")

    if messages:
        raise NASAAPIError(
            f"NASA POWER message: {messages}"
        )

    return _process_response(
        response_data=response_data,
        selected_variables=selected_variables,
        latitude=latitude,
        longitude=longitude,
        start_date=formatted_start,
        end_date=formatted_end,
    )


# ---------------------------------------------------------------------
# Single-variable helper
# ---------------------------------------------------------------------

def fetch_variable_data(
    variable_id: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch daily observations for one supported NASA POWER variable."""

    return fetch_daily_data(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        variable_ids=[variable_id],
    )


# ---------------------------------------------------------------------
# Basic module test
# ---------------------------------------------------------------------

if __name__ == "__main__":

    print("\nTRENDMATRIX AI - NASA POWER API TEST")
    print("=" * 55)

    print("Testing NASA POWER daily point-data connection...")

    try:
        test_dataframe = fetch_daily_data(
            latitude=33.4484,
            longitude=-112.0740,
            start_date="2020-01-01",
            end_date="2020-01-07",
            variable_ids=[
                "temperature",
                "humidity",
                "wind_speed",
                "precipitation",
                "solar_radiation",
            ],
        )

        print("\nNASA POWER connection successful.")

        print("\nLocation:")
        print(
            f"Latitude: {test_dataframe.attrs['latitude']}, "
            f"Longitude: {test_dataframe.attrs['longitude']}"
        )

        print("\nData preview:")
        print(test_dataframe.head())

        print("\nUnits:")

        for variable, unit in test_dataframe.attrs["units"].items():
            print(f"- {variable}: {unit}")

        print("\nTotal observations:", len(test_dataframe))
        print("Data source:", test_dataframe.attrs["source"])
        print("Data type:", test_dataframe.attrs["data_type"])
        print("Spatial type:", test_dataframe.attrs["spatial_type"])
        print("Frequency:", test_dataframe.attrs["frequency"])

        print("\nNASA POWER module tested successfully.")

    except (NASAAPIError, ValueError) as error:
        print("\nNASA POWER test failed.")
        print("Reason:", error)
