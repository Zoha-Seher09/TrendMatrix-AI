
"""
Earth Science Variable Catalogue for TrendMatrix AI.

This module defines supported Earth science variables,
their scientific descriptions, measurement units, and
recommended NASA data sources.

The catalogue is designed to support future NASA API
integrations and user-friendly variable discovery.
"""

# --------------------------------------------------
# Earth Science Variable Catalogue
# --------------------------------------------------

VARIABLES = {

    # --------------------------------------------------
    # ATMOSPHERE
    # --------------------------------------------------

    "temperature": {
        "name": "Air Temperature",
        "category": "Atmosphere",
        "description": (
            "Measures the temperature of air near the Earth's surface. "
            "Temperature trends help identify warming or cooling patterns."
        ),
        "unit": "°C",
        "source": "NASA POWER",
        "dataset": "NASA POWER Daily and Monthly",
        "parameter": "T2M",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Useful for studying climate change, heat patterns, "
            "and regional temperature variations."
        )
    },

    "humidity": {
        "name": "Relative Humidity",
        "category": "Atmosphere",
        "description": (
            "Measures the amount of moisture in the air relative "
            "to the maximum amount the air can hold at that temperature."
        ),
        "unit": "%",
        "source": "NASA POWER",
        "dataset": "NASA POWER Daily and Monthly",
        "parameter": "RH2M",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Helps investigate atmospheric moisture, drought conditions, "
            "and regional climate patterns."
        )
    },

    "wind_speed": {
        "name": "Wind Speed",
        "category": "Atmosphere",
        "description": (
            "Measures the speed of wind near the Earth's surface."
        ),
        "unit": "m/s",
        "source": "NASA POWER",
        "dataset": "NASA POWER Daily and Monthly",
        "parameter": "WS10M",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Useful for studying atmospheric circulation, "
            "wind energy potential, and changing weather patterns."
        )
    },

    # --------------------------------------------------
    # HYDROLOGY
    # --------------------------------------------------

    "precipitation": {
        "name": "Precipitation",
        "category": "Hydrology",
        "description": (
            "Measures the amount of water falling from the atmosphere "
            "as rain or other forms of precipitation."
        ),
        "unit": "mm/day",
        "source": "NASA POWER",
        "dataset": "NASA POWER Daily and Monthly",
        "parameter": "PRECTOTCORR",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Important for studying rainfall patterns, droughts, "
            "flood risks, and regional water availability."
        )
    },

    "soil_moisture": {
        "name": "Soil Moisture",
        "category": "Hydrology",
        "description": (
            "Measures the amount of water contained in soil. "
            "It influences vegetation growth, agriculture, and drought."
        ),
        "unit": "kg/m²",
        "source": "NASA GLDAS",
        "dataset": "GLDAS Land Surface Model",
        "parameter": "SoilMoi",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Helps investigate drought development, agricultural "
            "conditions, and changes in land water storage."
        )
    },

    "evapotranspiration": {
        "name": "Evapotranspiration",
        "category": "Hydrology",
        "description": (
            "Measures water transferred from the land surface "
            "to the atmosphere through evaporation and plant transpiration."
        ),
        "unit": "mm/day",
        "source": "NASA MODIS / GLDAS",
        "dataset": "MODIS or GLDAS Evapotranspiration Products",
        "parameter": "ET",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Useful for studying water cycles, vegetation water use, "
            "and changes in surface moisture."
        )
    },

    # --------------------------------------------------
    # LAND AND VEGETATION
    # --------------------------------------------------

    "ndvi": {
        "name": "Normalized Difference Vegetation Index",
        "category": "Vegetation",
        "description": (
            "NDVI measures vegetation greenness using reflected "
            "red and near-infrared light. Higher values generally "
            "indicate greener vegetation."
        ),
        "unit": "Index (-1 to +1)",
        "source": "NASA MODIS",
        "dataset": "MODIS MOD13Q1",
        "parameter": "NDVI",
        "frequency": ["16-DAY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Helps investigate vegetation health, greening, "
            "vegetation loss, and ecosystem changes."
        )
    },

    # --------------------------------------------------
    # ENERGY
    # --------------------------------------------------

    "solar_radiation": {
        "name": "Surface Solar Radiation",
        "category": "Energy",
        "description": (
            "Measures incoming solar energy received at the Earth's "
            "surface over a specified period."
        ),
        "unit": "kWh/m²/day",
        "source": "NASA POWER",
        "dataset": "NASA POWER Daily and Monthly",
        "parameter": "ALLSKY_SFC_SW_DWN",
        "frequency": ["DAILY", "MONTHLY"],
        "trend_direction": "Increasing or decreasing",
        "scientific_relevance": (
            "Useful for studying solar energy availability, "
            "cloud-related changes, and surface energy patterns."
        )
    }
}

# --------------------------------------------------
# Catalogue retrieval functions
# --------------------------------------------------

def get_all_variables() -> dict:
    """
    Return the complete Earth science variable catalogue.
    """

    return VARIABLES.copy()

def get_variable(variable_id: str):
    """
    Retrieve a variable using its unique identifier.

    Returns None if the requested variable does not exist.
    """

    if not isinstance(variable_id, str):
        return None

    return VARIABLES.get(variable_id.strip().lower())

def get_variables_by_category(category: str) -> dict:
    """
    Return all variables belonging to a specific category.
    """

    if not isinstance(category, str):
        return {}

    normalized_category = category.strip().lower()

    return {
        variable_id: details
        for variable_id, details in VARIABLES.items()
        if details["category"].lower() == normalized_category
    }

def get_all_categories() -> list:
    """
    Return a sorted list of unique variable categories.
    """

    return sorted({
        details["category"]
        for details in VARIABLES.values()
    })

def search_variables(keyword: str) -> dict:
    """
    Search variables by name, category, description,
    scientific relevance, or identifier.
    """

    if not isinstance(keyword, str) or not keyword.strip():
        return {}

    search_term = keyword.strip().lower()
    matching_variables = {}

    for variable_id, details in VARIABLES.items():

        searchable_content = " ".join([
            variable_id,
            details["name"],
            details["category"],
            details["description"],
            details["scientific_relevance"],
            details["source"]
        ]).lower()

        if search_term in searchable_content:
            matching_variables[variable_id] = details

    return matching_variables

def get_variables_by_source(source: str) -> dict:
    """
    Return variables associated with a NASA data source.
    """

    if not isinstance(source, str):
        return {}

    normalized_source = source.strip().lower()

    return {
        variable_id: details
        for variable_id, details in VARIABLES.items()
        if normalized_source in details["source"].lower()
    }

# --------------------------------------------------
# Catalogue summary
# --------------------------------------------------

def get_catalogue_summary() -> dict:
    """
    Return summary information about the variable catalogue.
    """

    category_counts = {}

    for details in VARIABLES.values():

        category = details["category"]

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

    return {
        "total_variables": len(VARIABLES),
        "total_categories": len(category_counts),
        "categories": category_counts,
        "supported_sources": sorted({
            details["source"]
            for details in VARIABLES.values()
        })
    }

# --------------------------------------------------
# Main execution
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 55)
    print("TRENDMATRIX AI - EARTH SCIENCE VARIABLE CATALOGUE")
    print("=" * 55)

    summary = get_catalogue_summary()

    print(f"\nTotal variables: {summary['total_variables']}")
    print(f"Total categories: {summary['total_categories']}")

    print("\nAvailable categories:")

    for category, count in summary["categories"].items():
        print(f"- {category}: {count} variable(s)")

    print("\nAvailable variables:")

    for variable_id, details in VARIABLES.items():
        print(
            f"- {details['name']} "
            f"({variable_id}) | Source: {details['source']}"
        )

    print("\nCatalogue loaded successfully.")