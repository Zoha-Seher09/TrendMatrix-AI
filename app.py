"""
TrendMatrix AI Flask application.

Connects NASA observations, cached data, offline demo data,
statistical analysis, Plotly visualization, Gemini explanations,
and scientific HTML reports.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

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
from data_storage import get_available_datasets
from services.location_service import search_photon_locations

from utils.common import to_dict

from services.analysis_service import run_analysis


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



# Gemini should not hold the entire dashboard request indefinitely.






# ---------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------



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





# ---------------------------------------------------------------------
# Statistical analysis
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# Gemini AI with a bounded wait
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# Scientific report
# ---------------------------------------------------------------------



# ---------------------------------------------------------------------
# Complete analysis pipeline
# ---------------------------------------------------------------------



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

        return jsonify(run_analysis(payload, CHARTS_DIR, REPORTS_DIR))

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