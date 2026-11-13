"""
TrendMatrix AI Flask application.

Connects NASA observations, cached data, offline demo data,
statistical analysis, Plotly visualization, Gemini explanations,
and scientific HTML reports.
"""

from __future__ import annotations

import logging
import threading
import queue
import time

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

from config import Config
from database import init_db
from data_storage import (
    fetch_and_store_dataset,
    get_stored_dataset,
    get_available_datasets,
)
from offline_manager import get_offline_dataset
from statistical_analysis import analyze_trend
from visualization import create_time_series_chart, save_chart_html
from ai_explainer import explain_analysis
from report_generator import generate_report
from services.location_service import search_photon_locations
from utils.common import (
    to_dict,
    safe_filename,
    call_compatible,
    json_safe,
)


# ---------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = DATA_DIR / "charts"
REPORTS_DIR = DATA_DIR / "reports"

CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("trendmatrix")

init_db()

SUPPORTED_VARIABLES = {
    "temperature": "Air Temperature",
    "humidity": "Relative Humidity",
    "wind_speed": "Wind Speed",
    "precipitation": "Precipitation",
    "soil_moisture": "Soil Moisture",
    "evapotranspiration": "Evapotranspiration",
    "ndvi": "Normalized Difference Vegetation Index (NDVI)",
    "solar_radiation": "Solar Radiation",
}


# Gemini should not hold the entire dashboard request indefinitely.
GEMINI_WAIT_SECONDS = 18


def filter_requested_dates(
    dataframe: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Keep observations within the requested date range."""

    result = dataframe.copy()

    index = pd.to_datetime(result.index, errors="coerce")
    valid = ~index.isna()

    result = result.loc[valid].copy()
    result.index = index[valid]

    start = pd.Timestamp(start_date)
    end = (
        pd.Timestamp(end_date)
        + pd.Timedelta(days=1)
        - pd.Timedelta(microseconds=1)
    )

    return result.loc[
        (result.index >= start) & (result.index <= end)
    ].sort_index()


def prepare_requested_frequency(
    dataframe: pd.DataFrame,
    variable_id: str,
    frequency: str,
    metadata: dict,
) -> tuple[pd.DataFrame, dict]:
    """
    Aggregate daily observations into monthly observations when requested.

    Precipitation is accumulated; other variables use monthly means.
    """

    result = dataframe.copy()
    updated_metadata = dict(metadata)

    if frequency == "monthly":

        result.index = pd.to_datetime(result.index, errors="coerce")
        result = result.loc[~result.index.isna()]

        if variable_id not in result.columns:
            raise ValueError(
                f"Variable '{variable_id}' is missing from the dataset."
            )

        if variable_id == "precipitation":
            result = result[[variable_id]].resample("MS").sum(
                min_count=1
            )

            updated_metadata["unit"] = "mm/month"

        else:
            result = result[[variable_id]].resample("MS").mean()

        result = result.dropna(subset=[variable_id])

    else:
        result = result.sort_index()

    if result.empty:
        raise ValueError(
            "No valid observations remain after frequency processing."
        )

    updated_metadata["frequency"] = frequency
    updated_metadata["observation_count"] = len(result)

    result.attrs.update(updated_metadata)

    return result, updated_metadata


# ---------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------

def validate_request_data(payload: dict):

    variable_id = str(
        payload.get("variable", "")
    ).strip().lower()

    region_name = str(
        payload.get("region", "")
    ).strip()

    start_date = str(
        payload.get("start_date", "")
    ).strip()

    end_date = str(
        payload.get("end_date", "")
    ).strip()

    frequency = str(
        payload.get("frequency", "monthly")
    ).strip().lower()

    if variable_id not in SUPPORTED_VARIABLES:
        return {}, "Please select a supported Earth science variable."

    if not region_name:
        return {}, "Please select a location from the suggestions."

    if frequency not in {"daily", "monthly"}:
        return {}, "Frequency must be daily or monthly."

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

    except ValueError:
        return {}, "Please select valid start and end dates."

    if start >= end:
        return {}, "End date must be later than start date."

    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))

    except (TypeError, ValueError):
        return {}, "Please select a location from the suggestions."

    if not -90 <= latitude <= 90:
        return {}, "Invalid latitude."

    if not -180 <= longitude <= 180:
        return {}, "Invalid longitude."

    return {
        "variable_id": variable_id,
        "variable_name": SUPPORTED_VARIABLES[variable_id],
        "region_name": region_name,
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "frequency": frequency,
    }, None


@app.get("/api/geocode")
def geocode_location():

    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify({
            "success": True,
            "results": [],
        })

    if len(query) > 120:
        return jsonify({
            "success": False,
            "error": "Search text is too long.",
        }), 400

    try:

        results = search_photon_locations(query)

        return jsonify({
            "success": True,
            "count": len(results),
            "results": results,
        })

    except requests.Timeout:

        return jsonify({
            "success": False,
            "error": "Location search timed out. Please try again.",
        }), 504

    except requests.RequestException as exc:

        logger.warning("Photon location search failed: %s", exc)

        return jsonify({
            "success": False,
            "error": (
                "Global location search is temporarily unavailable. "
                "Please check your internet connection and try again."
            ),
        }), 503

    except (ValueError, KeyError, TypeError) as exc:

        logger.exception("Location response error: %s", exc)

        return jsonify({
            "success": False,
            "error": "Could not process location search results.",
        }), 502


# ---------------------------------------------------------------------
# Dataset retrieval
# ---------------------------------------------------------------------

def build_dataframe_from_stored_dataset(
    dataset_id: int,
) -> tuple[pd.DataFrame, dict]:

    result = get_stored_dataset(dataset_id)

    if not result:
        raise ValueError("Stored dataset could not be retrieved.")

    result = to_dict(result)

    metadata = to_dict(result.get("dataset"))
    observations = result.get("observations", [])

    if not observations:
        raise ValueError("Stored dataset contains no observations.")

    dataframe = pd.DataFrame([
        to_dict(item) for item in observations
    ])

    if not {"date", "value"}.issubset(dataframe.columns):
        raise ValueError(
            "Stored observations are missing date or value fields."
        )

    dataframe["date"] = pd.to_datetime(
        dataframe["date"],
        errors="coerce",
    )

    dataframe["value"] = pd.to_numeric(
        dataframe["value"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["date", "value"]
    ).sort_values("date")

    if dataframe.empty:
        raise ValueError("No valid observations were found.")

    variable_id = (
        metadata.get("variable_id")
        or metadata.get("variable")
        or "temperature"
    )

    dataframe = (
        dataframe.set_index("date")[["value"]]
        .rename(columns={"value": variable_id})
    )

    return dataframe, metadata


def retrieve_dataset(payload: dict):

    variable_id = payload["variable_id"]
    live_error = None

    logger.info(
        "Starting NASA retrieval: %s | %s",
        variable_id,
        payload["region_name"],
    )

    # First priority: live NASA observations.
    try:

        live_result = fetch_and_store_dataset(
            variable_id=variable_id,
            latitude=payload["latitude"],
            longitude=payload["longitude"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            region_name=payload["region_name"],
            frequency=payload["frequency"],
        )

        if (
            live_result
            and live_result.get("success")
            and live_result.get("dataset_id") is not None
        ):

            dataframe, stored_metadata = (
                build_dataframe_from_stored_dataset(
                    int(live_result["dataset_id"])
                )
            )

            dataframe = filter_requested_dates(
                dataframe,
                payload["start_date"],
                payload["end_date"],
            )

            if dataframe.empty:
                raise ValueError(
                    "NASA returned no observations in this date range."
                )

            metadata = {
                **stored_metadata,
                **live_result,
                "variable": variable_id,
                "variable_name": payload["variable_name"],
                "region": payload["region_name"],
                "latitude": payload["latitude"],
                "longitude": payload["longitude"],
                "frequency": payload["frequency"],
                "data_type": "live_nasa",
                "source_label": "Live NASA POWER Observations",
                "is_sample": False,
                "spatial_type": "point",
            }

            dataframe.attrs.update(metadata)

            logger.info(
                "NASA retrieval completed: %s observations",
                len(dataframe),
            )

            return dataframe, metadata, "live_nasa"

        live_error = (
            live_result or {}
        ).get(
            "message",
            "NASA did not return a usable dataset.",
        )

        logger.warning("NASA retrieval unavailable: %s", live_error)

    except Exception as exc:

        live_error = str(exc)

        logger.exception("NASA retrieval failed: %s", exc)

    # Second priority: previously cached NASA data or labelled demo data.
    try:

        start = date.fromisoformat(payload["start_date"])

        years = max(
            1,
            date.today().year - start.year + 1,
        )

        offline_result = get_offline_dataset(
            variable_id=variable_id,
            region_name=payload["region_name"],
            years=years,
            frequency=payload["frequency"],
            latitude=payload["latitude"],
            longitude=payload["longitude"],
        )

        if (
            not offline_result
            or not offline_result.get("success")
        ):
            raise ValueError(
                (offline_result or {}).get(
                    "message",
                    "Offline retrieval failed.",
                )
            )

        dataframe = offline_result["data"].copy()

        dataframe = filter_requested_dates(
            dataframe,
            payload["start_date"],
            payload["end_date"],
        )

        if dataframe.empty:
            raise ValueError(
                "No offline observations match the selected date range."
            )

        metadata = dict(
            offline_result.get("metadata") or {}
        )

        data_type = offline_result.get(
            "data_type",
            metadata.get("data_type", "sample_demo"),
        )

        if data_type == "cached_nasa":

            cached_region = str(
                metadata.get("region")
                or metadata.get("region_name")
                or ""
            ).strip().casefold()

            requested_region = (
                payload["region_name"].strip().casefold()
            )

            if (
                cached_region
                and cached_region != requested_region
            ):
                raise ValueError(
                    "Cached NASA data belongs to a different region."
                )

        metadata.update({
            "variable": variable_id,
            "variable_name": payload["variable_name"],
            "region": payload["region_name"],
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
            "frequency": payload["frequency"],
            "data_type": data_type,
            "source_label": offline_result.get(
                "source_label",
                metadata.get(
                    "source_label",
                    "Synthetic Demo Data",
                ),
            ),
            "live_nasa_error": live_error,
            "spatial_type": metadata.get("spatial_type", "point"),
        })

        dataframe.attrs.update(metadata)

        return dataframe, metadata, data_type

    except Exception as exc:

        logger.exception("Offline retrieval failed: %s", exc)

        raise RuntimeError(
            "NASA retrieval failed and no suitable offline "
            f"dataset was available: {exc}"
        ) from exc


# ---------------------------------------------------------------------
# Statistical analysis
# ---------------------------------------------------------------------

def run_statistical_analysis(
    dataframe: pd.DataFrame,
    variable_id: str,
    unit: str,
    frequency: str,
) -> dict:

    values = {
        "dataframe": dataframe,
        "df": dataframe,
        "series": dataframe[variable_id],
        "data": dataframe,
        "variable": variable_id,
        "variable_id": variable_id,
        "unit": unit,
        "frequency": frequency,
    }

    result = call_compatible(
        analyze_trend,
        values,
        {
            "time_series": "series",
            "observations": "dataframe",
        },
    )

    if not isinstance(result, dict) or result.get("success") is False:

        raise RuntimeError(
            (result or {}).get(
                "message",
                "Statistical analysis failed.",
            )
        )

    return json_safe(result)


# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------

def generate_visualization(
    dataframe: pd.DataFrame,
    variable_id: str,
    variable_name: str,
    region_name: str,
    unit: str,
    metadata: dict,
) -> str:

    chart = call_compatible(
        create_time_series_chart,
        {
            "dataframe": dataframe,
            "df": dataframe,
            "data": dataframe,
            "variable": variable_id,
            "variable_id": variable_id,
            "title": f"{variable_name} Trend - {region_name}",
            "unit": unit,
            "source_label": metadata.get("source_label"),
            "metadata": metadata,
        },
    )

    filename = (
        f"trendmatrix_chart_{safe_filename(variable_id)}_"
        f"{safe_filename(region_name)}_"
        f"{datetime.now():%Y%m%d_%H%M%S}.html"
    )

    output_path = CHARTS_DIR / filename

    call_compatible(
        save_chart_html,
        {
            "chart": chart,
            "figure": chart,
            "fig": chart,
            "output_path": output_path,
            "file_path": output_path,
            "filepath": output_path,
            "path": output_path,
        },
    )

    if not output_path.exists():
        raise RuntimeError(
            "Visualization module did not create the chart file."
        )

    return filename


# ---------------------------------------------------------------------
# Gemini AI with a bounded wait
# ---------------------------------------------------------------------

def generate_ai_explanation(
    analysis: dict,
    metadata: dict,
) -> dict:
    """
    Run Gemini in a daemon thread.

    If Gemini is slow or unavailable, the scientific analysis and report
    can still be returned without waiting indefinitely.
    """

    result_queue = queue.Queue(maxsize=1)

    def worker():

        try:
            result = explain_analysis(
                analysis=analysis,
                metadata=metadata,
            )

            if isinstance(result, dict):
                result_queue.put(json_safe(result))
            else:
                result_queue.put({
                    "success": True,
                    "explanation": str(result),
                })

        except Exception as exc:

            result_queue.put({
                "success": False,
                "error": str(exc),
                "explanation": (
                    "Gemini AI is temporarily unavailable. "
                    "Verified statistical results were calculated "
                    "independently using Python."
                ),
            })

    thread = threading.Thread(
        target=worker,
        daemon=True,
    )

    thread.start()
    thread.join(GEMINI_WAIT_SECONDS)

    if thread.is_alive():

        logger.warning(
            "Gemini exceeded the %s-second wait limit.",
            GEMINI_WAIT_SECONDS,
        )

        return {
            "success": False,
            "timeout": True,
            "explanation": (
                "Gemini did not respond within the waiting period. "
                "The statistical analysis is still valid and was "
                "calculated independently using Python."
            ),
        }

    try:
        return result_queue.get_nowait()

    except queue.Empty:

        return {
            "success": False,
            "explanation": (
                "Gemini explanation is unavailable. "
                "Python statistical results remain available."
            ),
        }


# ---------------------------------------------------------------------
# Scientific report
# ---------------------------------------------------------------------

def generate_scientific_report(
    analysis: dict,
    metadata: dict,
    dataframe: pd.DataFrame,
    ai_result: dict,
) -> dict:

    result = call_compatible(
        generate_report,
        {
            "analysis": analysis,
            "analysis_result": analysis,
            "statistical_results": analysis,
            "results": analysis,
            "metadata": metadata,
            "dataset_metadata": metadata,
            "dataframe": dataframe,
            "data": dataframe,
            "ai_explanation": ai_result,
            "ai_result": ai_result,
            "output_dir": REPORTS_DIR,
            "report_dir": REPORTS_DIR,
            "directory": REPORTS_DIR,
            "format": "html",
            "report_format": "html",
        },
    )

    if isinstance(result, dict):
        report = dict(result)

    elif isinstance(result, (str, Path)):

        path = Path(result)

        report = {
            "success": path.exists(),
            "file_path": str(path),
            "filename": path.name,
        }

    else:

        report = {
            "success": False,
            "message": "Unexpected report-generator response.",
        }

    raw_filename = (
        report.get("filename")
        or report.get("file_path")
    )

    if raw_filename:

        filename = Path(raw_filename).name

        report.update({
            "filename": filename,
            "url": f"/reports/{filename}",
        })

    return json_safe(report)


# ---------------------------------------------------------------------
# Complete analysis pipeline
# ---------------------------------------------------------------------

def run_analysis(payload: dict) -> dict:

    request_data, error = validate_request_data(payload)

    if error:
        raise ValueError(error)

    started_at = time.monotonic()

    logger.info(
        "Analysis started: %s | %s | %s",
        request_data["variable_id"],
        request_data["region_name"],
        request_data["frequency"],
    )

    # Stage 1: retrieve observations.
    dataframe, metadata, data_type = retrieve_dataset(
        request_data
    )

    if dataframe.empty:
        raise ValueError("The selected dataset contains no observations.")

    # Stage 2: apply the requested frequency.
    dataframe, metadata = prepare_requested_frequency(
        dataframe,
        request_data["variable_id"],
        request_data["frequency"],
        metadata,
    )

    variable_id = request_data["variable_id"]

    unit = str(
        metadata.get("unit")
        or metadata.get("units")
        or "unknown"
    )

    logger.info(
        "Prepared %s observations for statistical analysis.",
        len(dataframe),
    )

    # Stage 3: verified Python statistical calculations.
    analysis = run_statistical_analysis(
        dataframe,
        variable_id,
        unit,
        request_data["frequency"],
    )

    # Stage 4: chart generation.
    chart_filename = generate_visualization(
        dataframe,
        variable_id,
        request_data["variable_name"],
        request_data["region_name"],
        unit,
        metadata,
    )

    # Stage 5: bounded-wait AI explanation.
    ai_result = generate_ai_explanation(
        analysis,
        metadata,
    )

    # Stage 6: scientific report.
    report_result = generate_scientific_report(
        analysis,
        metadata,
        dataframe,
        ai_result,
    )

    elapsed = round(
        time.monotonic() - started_at,
        2,
    )

    logger.info(
        "Analysis completed in %s seconds.",
        elapsed,
    )

    return json_safe({
        "success": True,
        "variable": variable_id,
        "variable_name": request_data["variable_name"],
        "region": request_data["region_name"],
        "frequency": request_data["frequency"],
        "start_date": request_data["start_date"],
        "end_date": request_data["end_date"],
        "observation_count": int(len(dataframe)),
        "data_type": data_type,
        "source_label": metadata.get(
            "source_label",
            "Unknown data source",
        ),
        "unit": unit,
        "processing_seconds": elapsed,
        "metadata": metadata,
        "analysis": analysis,
        "ai_explanation": ai_result,
        "chart": {
            "filename": chart_filename,
            "url": f"/charts/{chart_filename}",
        },
        "report": report_result,
    })


# ---------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------




# ---------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------

@app.get("/")
def dashboard():

    return render_template("dashboard.html")


@app.get("/health")
def health():

    return jsonify({
        "success": True,
        "application": "TrendMatrix AI",
        "status": "running",
    })


@app.get("/api/datasets")
def list_datasets():

    try:

        datasets = get_available_datasets()

        return jsonify({
            "success": True,
            "count": len(datasets),
            "datasets": [
                to_dict(item) for item in datasets
            ],
        })

    except Exception as exc:

        logger.exception(
            "Dataset listing failed: %s",
            exc,
        )

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.post("/api/analyze")
def analyze():

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):

        return jsonify({
            "success": False,
            "error": "A valid JSON request body is required.",
        }), 400

    try:

        return jsonify(run_analysis(payload))

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    except Exception as exc:

        logger.exception(
            "TrendMatrix analysis failed: %s",
            exc,
        )

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.get("/charts/<path:filename>")
def open_chart_file(filename: str):

    return send_from_directory(
        CHARTS_DIR,
        filename,
    )


@app.get("/reports/<path:filename>")
def open_report_file(filename: str):

    return send_from_directory(
        REPORTS_DIR,
        filename,
    )


@app.errorhandler(404)
def not_found(_error):

    return jsonify({
        "success": False,
        "error": "The requested resource was not found.",
    }), 404


@app.errorhandler(500)
def internal_error(_error):

    return jsonify({
        "success": False,
        "error": (
            "An internal server error occurred. "
            "Check the application terminal for details."
        ),
    }), 500


# ---------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=bool(getattr(Config, "DEBUG", False)),
        threaded=True,
    )