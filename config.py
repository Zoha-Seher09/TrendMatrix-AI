
"""
Application configuration for TrendMatrix AI.

This module centralizes application settings, environment variables,
database paths, NASA API configuration, and AI integration settings.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# --------------------------------------------------
# Project directories
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_DATA_DIR = DATA_DIR / "samples"


# Create required directories if they do not exist.
for directory in (DATA_DIR, CACHE_DIR, SAMPLE_DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Environment configuration
# --------------------------------------------------

ENV_FILE = BASE_DIR / ".env"

# Load environment variables from the project root .env file.
load_dotenv(dotenv_path=ENV_FILE, override=False)


def get_bool_env(name: str, default: bool = False) -> bool:
    """Read a boolean value from an environment variable."""

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in ("true", "1", "yes", "on")


# --------------------------------------------------
# Flask application settings
# --------------------------------------------------

class Config:
    """Base configuration for the Flask application."""

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "development-secret-key-change-before-deployment"
    )

    DEBUG = get_bool_env("FLASK_DEBUG", False)

    JSON_SORT_KEYS = False

    # Maximum request payload size: 10 MB.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024


# --------------------------------------------------
# Database configuration
# --------------------------------------------------

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        str(DATA_DIR / "trendmatrix.db")
    )
)

# SQLite database file used for persistent data storage.
SQLITE_DATABASE_URI = f"sqlite:///{DATABASE_PATH.as_posix()}"


# --------------------------------------------------
# NASA data configuration
# --------------------------------------------------

NASA_POWER_BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal"
)

NASA_REQUEST_TIMEOUT = int(
    os.getenv("NASA_REQUEST_TIMEOUT", "30")
)


# --------------------------------------------------
# Gemini AI configuration
# --------------------------------------------------

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

# Expose Gemini settings through the Flask Config class.
# This allows other modules to access Config.GEMINI_API_KEY.
Config.GEMINI_API_KEY = GEMINI_API_KEY
Config.GEMINI_MODEL = GEMINI_MODEL


# --------------------------------------------------
# Offline mode configuration
# --------------------------------------------------

OFFLINE_MODE_ENABLED = get_bool_env(
    "OFFLINE_MODE_ENABLED",
    True
)

USE_SAMPLE_DATA_AS_FALLBACK = get_bool_env(
    "USE_SAMPLE_DATA_AS_FALLBACK",
    True
)

# Cached NASA observations remain available without internet.
CACHE_ENABLED = True


# --------------------------------------------------
# Data processing configuration
# --------------------------------------------------

DEFAULT_DATA_FREQUENCY = "MONTHLY"

SUPPORTED_DATA_FREQUENCIES = (
    "DAILY",
    "MONTHLY"
)

DEFAULT_ANALYSIS_CONFIDENCE = 0.95

DEFAULT_P_VALUE_THRESHOLD = 0.05

# Timeout used for external API requests.
API_REQUEST_TIMEOUT = 30
