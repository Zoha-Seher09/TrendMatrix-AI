"""
TrendMatrix AI - Analysis Service.

Coordinates NASA data retrieval, offline fallback, statistical analysis,
visualization, AI explanations, and scientific report generation.
"""

import logging
import queue
import threading
import time

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from ai_explainer import explain_analysis
from data_storage import fetch_and_store_dataset, get_stored_dataset
from offline_manager import get_offline_dataset
from report_generator import generate_report
from services.request_validation import (
    filter_requested_dates,
    prepare_requested_frequency,
    validate_request_data,
)
from statistical_analysis import analyze_trend
from utils.common import call_compatible, json_safe, safe_filename, to_dict
from variables import get_all_variables
from visualization import create_time_series_chart, save_chart_html


logger = logging.getLogger("trendmatrix")

GEMINI_WAIT_SECONDS = 18

SUPPORTED_VARIABLES = {
    variable_id: variable_data["name"]
    for variable_id, variable_data in get_all_variables().items()
}


def build_dataframe_from_stored_dataset(
    dataset_id: int,
) -> tuple[pd.DataFrame, dict]:
    """Convert stored database observations into a time-series DataFrame."""

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
    """
    Retrieve live NASA observations first.

    If live retrieval fails, use a matching cached NASA dataset or
    clearly labelled synthetic demo data.
    """

    variable_id = payload["variable_id"]
    live_error = None

    logger.info(
        "Starting NASA retrieval: %s | %s",
        variable_id,
        payload["region_name"],
    )

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


def run_statistical_analysis(
    dataframe: pd.DataFrame,
    variable_id: str,
    unit: str,
    frequency: str,
) -> dict:
    """Run the project's configured scientific trend analysis."""

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


def generate_visualization(
    dataframe: pd.DataFrame,
    variable_id: str,
    variable_name: str,
    region_name: str,
    unit: str,
    metadata: dict,
    charts_dir: Path,
) -> str:
    """Generate and save the time-series chart."""

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

    output_path = charts_dir / filename

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


def generate_ai_explanation(
    analysis: dict,
    metadata: dict,
) -> dict:
    """
    Run Gemini in a daemon thread with a bounded waiting period.

    Scientific results remain available if Gemini is slow or unavailable.
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


def generate_scientific_report(
    analysis: dict,
    metadata: dict,
    dataframe: pd.DataFrame,
    ai_result: dict,
    reports_dir: Path,
) -> dict:
    """Generate the scientific HTML report."""

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
            "output_dir": reports_dir,
            "report_dir": reports_dir,
            "directory": reports_dir,
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


def run_analysis(
    payload: dict,
    charts_dir: Path,
    reports_dir: Path,
) -> dict:
    """Execute the complete TrendMatrix analysis pipeline."""

    request_data, error = validate_request_data(
        payload,
        SUPPORTED_VARIABLES,
    )

    if error:
        raise ValueError(error)

    started_at = time.monotonic()

    logger.info(
        "Analysis started: %s | %s | %s",
        request_data["variable_id"],
        request_data["region_name"],
        request_data["frequency"],
    )

    dataframe, metadata, data_type = retrieve_dataset(
        request_data
    )

    if dataframe.empty:
        raise ValueError("The selected dataset contains no observations.")

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

    analysis = run_statistical_analysis(
        dataframe,
        variable_id,
        unit,
        request_data["frequency"],
    )

    chart_filename = generate_visualization(
        dataframe,
        variable_id,
        request_data["variable_name"],
        request_data["region_name"],
        unit,
        metadata,
        charts_dir,
    )

    ai_result = generate_ai_explanation(
        analysis,
        metadata,
    )

    report_result = generate_scientific_report(
        analysis,
        metadata,
        dataframe,
        ai_result,
        reports_dir,
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
