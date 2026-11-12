
"""
SQLite database management for TrendMatrix AI.

This module handles database initialization, dataset metadata,
NASA observations, and offline data retrieval.
"""

import json
import sqlite3
import math

from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Create and return a SQLite database connection.

    Foreign key support and dictionary-style row access
    are enabled for every connection.
    """

    database_file = Path(DATABASE_PATH)
    database_file.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(database_file),
        timeout=30
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")

    return connection


# --------------------------------------------------
# Database initialization
# --------------------------------------------------

def init_db() -> None:
    """
    Create all required database tables and indexes.

    Existing data is preserved when the application
    initializes the database again.
    """

    with get_connection() as connection:

        # Stores information about each downloaded dataset.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variable_name TEXT NOT NULL,
                variable_code TEXT,
                description TEXT,
                unit TEXT,
                data_source TEXT NOT NULL,
                region_name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                frequency TEXT NOT NULL,
                data_type TEXT NOT NULL DEFAULT 'NASA',
                is_sample INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT,
                fetched_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Stores individual time-series observations.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                observation_date TEXT NOT NULL,
                value REAL NOT NULL,
                quality_flag TEXT,
                FOREIGN KEY (dataset_id)
                    REFERENCES datasets(id)
                    ON DELETE CASCADE,
                UNIQUE(dataset_id, observation_date)
            )
        """)

        # Indexes improve historical data retrieval.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dataset_variable
            ON datasets(variable_name)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dataset_region
            ON datasets(region_name)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_observation_date
            ON observations(observation_date)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_observation_dataset
            ON observations(dataset_id)
        """)

        connection.commit()


# --------------------------------------------------
# Dataset management
# --------------------------------------------------

def save_dataset(dataset: dict) -> int:
    """
    Save dataset metadata and return its database ID.

    Required fields:
        variable_name, data_source, region_name,
        start_date, end_date, frequency

    Optional fields include units, coordinates,
    descriptions, and additional metadata.
    """

    required_fields = [
        "variable_name",
        "data_source",
        "region_name",
        "start_date",
        "end_date",
        "frequency"
    ]

    for field in required_fields:
        if not dataset.get(field):
            raise ValueError(
                f"Missing required dataset field: {field}"
            )

    now = datetime.now().astimezone().isoformat()

    metadata_json = json.dumps(
        dataset.get("metadata", {}),
        ensure_ascii=False
    )

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO datasets (
                variable_name,
                variable_code,
                description,
                unit,
                data_source,
                region_name,
                latitude,
                longitude,
                start_date,
                end_date,
                frequency,
                data_type,
                is_sample,
                metadata_json,
                fetched_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset["variable_name"],
            dataset.get("variable_code"),
            dataset.get("description"),
            dataset.get("unit"),
            dataset["data_source"],
            dataset["region_name"],
            dataset.get("latitude"),
            dataset.get("longitude"),
            dataset["start_date"],
            dataset["end_date"],
            dataset["frequency"],
            dataset.get("data_type", "NASA"),
            int(dataset.get("is_sample", False)),
            metadata_json,
            now,
            now
        ))

        connection.commit()

        return cursor.lastrowid


# --------------------------------------------------
# Observation management
# --------------------------------------------------

def save_observations(
    dataset_id: int,
    observations: list[dict]
) -> int:
    """
    Save time-series observations for a dataset.

    Each observation must contain:
        date: ISO-format date string
        value: numeric measurement

    Existing observations for the same dataset and date
    are updated instead of duplicated.
    """

    if not observations:
        return 0

    prepared_records = []

    for observation in observations:

        observation_date = observation.get("date")
        value = observation.get("value")

        if not observation_date or value is None:
            raise ValueError(
                "Every observation requires a date and value."
            )

        # Validate the date format.
        try:
            datetime.fromisoformat(str(observation_date))
        except ValueError as error:
            raise ValueError(
                f"Invalid observation date: {observation_date}"
            ) from error

        # Reject invalid numerical values.
        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            raise ValueError(
                "Observation values must be finite numbers."
            )

        prepared_records.append((
            dataset_id,
            str(observation_date),
            numeric_value,
            observation.get("quality_flag")
        ))

    with get_connection() as connection:

        # Confirm that the parent dataset exists.
        dataset_exists = connection.execute(
            "SELECT id FROM datasets WHERE id = ?",
            (dataset_id,)
        ).fetchone()

        if dataset_exists is None:
            raise ValueError(
                f"Dataset with ID {dataset_id} does not exist."
            )

        connection.executemany("""
            INSERT INTO observations (
                dataset_id,
                observation_date,
                value,
                quality_flag
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(dataset_id, observation_date)
            DO UPDATE SET
                value = excluded.value,
                quality_flag = excluded.quality_flag
        """, prepared_records)

        connection.commit()

    return len(prepared_records)


# --------------------------------------------------
# Dataset retrieval
# --------------------------------------------------

def get_dataset(dataset_id: int) -> Optional[dict]:
    """Retrieve one dataset using its database ID."""

    with get_connection() as connection:

        row = connection.execute("""
            SELECT *
            FROM datasets
            WHERE id = ?
        """, (dataset_id,)).fetchone()

        return dict(row) if row else None


def list_datasets(
    variable_name: Optional[str] = None,
    region_name: Optional[str] = None
) -> list[dict]:
    """
    Return available datasets.

    Optional filters allow searching by variable and region.
    """

    query = "SELECT * FROM datasets WHERE 1 = 1"
    parameters = []

    if variable_name:
        query += " AND variable_name = ?"
        parameters.append(variable_name)

    if region_name:
        query += " AND region_name = ?"
        parameters.append(region_name)

    query += " ORDER BY fetched_at DESC"

    with get_connection() as connection:

        rows = connection.execute(
            query,
            parameters
        ).fetchall()

        return [dict(row) for row in rows]


# --------------------------------------------------
# Offline observation retrieval
# --------------------------------------------------

def get_observations(dataset_id: int) -> list[dict]:
    """
    Retrieve cached observations for offline analysis.

    Results are returned in chronological order.
    """

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT
                observation_date,
                value,
                quality_flag
            FROM observations
            WHERE dataset_id = ?
            ORDER BY observation_date ASC
        """, (dataset_id,)).fetchall()

        return [dict(row) for row in rows]


# --------------------------------------------------
# Database statistics
# --------------------------------------------------

def get_database_stats() -> dict:
    """Return basic database storage statistics."""

    with get_connection() as connection:

        dataset_count = connection.execute(
            "SELECT COUNT(*) FROM datasets"
        ).fetchone()[0]

        observation_count = connection.execute(
            "SELECT COUNT(*) FROM observations"
        ).fetchone()[0]

        cached_count = connection.execute("""
            SELECT COUNT(*)
            FROM datasets
            WHERE is_sample = 0
        """).fetchone()[0]

        sample_count = connection.execute("""
            SELECT COUNT(*)
            FROM datasets
            WHERE is_sample = 1
        """).fetchone()[0]

        return {
            "total_datasets": dataset_count,
            "total_observations": observation_count,
            "cached_nasa_datasets": cached_count,
            "sample_datasets": sample_count
        }


# --------------------------------------------------
# Main execution
# --------------------------------------------------

if __name__ == "__main__":

    init_db()

    print("TrendMatrix AI database initialized successfully.")

    statistics = get_database_stats()

    print("Database statistics:")

    for key, value in statistics.items():
        print(f"{key}: {value}")
