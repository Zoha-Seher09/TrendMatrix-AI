
"""
Database package for TrendMatrix AI.

Exports database functions for use across the application.
"""

from .database import (
    get_connection,
    init_db,
    save_dataset,
    save_observations,
    get_dataset,
    list_datasets,
    get_observations,
    get_database_stats,
)

__all__ = [
    "get_connection",
    "init_db",
    "save_dataset",
    "save_observations",
    "get_dataset",
    "list_datasets",
    "get_observations",
    "get_database_stats",
]
