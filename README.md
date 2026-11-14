# TrendMatrix AI

### Earth Systems Trend Intelligence Platform

**Explore Earth. Detect Trends. Understand Change.**

*Powered by NASA Earth Observation Data*

## Overview

TrendMatrix AI is an interactive platform developed for the NASA Space Apps Challenge. It helps users explore historical Earth observation data, visualize environmental time series, and investigate long-term trends using statistical methods.

## Key Features

- Interactive 3D Earth globe for geographic selection.
- Location search and coordinate selection.
- Historical NASA POWER data retrieval.
- Daily and monthly time-series analysis.
- Statistical trend detection and significance testing.
- Interactive Plotly charts.
- Automated scientific HTML reports.
- Optional Gemini AI explanations.
- Configurable offline fallback using cached or sample data.

## Supported Live Variables

The current NASA POWER analysis pipeline supports:

- Air Temperature
- Relative Humidity
- Wind Speed
- Precipitation
- Solar Radiation

The broader catalogue also includes Soil Moisture, Evapotranspiration, and NDVI. These have been explored through separate NASA AppEEARS investigations but are not currently integrated into the live NASA POWER analysis pipeline.

## Statistical Methods

- Linear Regression
- Student's t-test
- Mann-Kendall Trend Test
- Sen's Slope Estimator
- Confidence Intervals
- Seasonal Mann-Kendall Analysis
- Lag-1 Residual Autocorrelation Diagnostics
- Newey-West HAC Standard Errors

Statistical significance does not establish causation. Results should be interpreted in the context of data coverage, seasonality, and autocorrelation.

## How It Works

1. Select an environmental variable.
2. Search for a location or select coordinates on the globe.
3. Choose a date range and data frequency.
4. Retrieve and process available observations.
5. Run statistical trend analysis.
6. Explore charts and scientific reports.

## Technology Stack

| Area | Technologies |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Data Processing | Pandas, NumPy |
| Statistics | SciPy, Statsmodels, pymannkendall |
| Visualization | Plotly, Globe.gl |
| Database | SQLite |
| Data Sources | NASA POWER, NASA AppEEARS |
| Geocoding | Photon |
| Optional AI | Google Gemini API |

## Installation

**Requirements:** Python 3.10 or newer, Git, and an internet connection.

Clone the repository:

```bash
git clone https://github.com/Zoha-Seher09/TrendMatrix-AI.git
cd TrendMatrix-AI
```

Create and activate a virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root. Example:

```env
SECRET_KEY=replace-with-a-secure-random-secret
FLASK_DEBUG=false
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
OFFLINE_MODE_ENABLED=true
USE_SAMPLE_DATA_AS_FALLBACK=true
NASA_REQUEST_TIMEOUT=30
```

The Gemini API key is optional. Never publish real API keys or credentials.

Start the application:

```bash
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## NASA Data Sources

- [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)
- [NASA POWER API Tutorials](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/)
- [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/)
- [NASA AppEEARS Data Resources](https://github.com/nasa/AppEEARS-Data-Resources)

## Scientific Considerations

- Live NASA POWER observations are point-based for selected coordinates, not regional spatial averages.
- The globe is a geographic selector, not a NASA satellite raster or data-layer map.
- Only five variables are currently supported by the live NASA POWER analysis pipeline.
- Data availability varies by variable, location, and date range.
- Cached or sample fallback data must be distinguished from live NASA observations.
- The globe and Earth texture use external public CDNs and require internet access.

## Intended Impact

TrendMatrix AI aims to make Earth science data and environmental trend investigation more accessible to students, educators, researchers, data analysts, and the public.

## Copyright and Ownership

Copyright (c) 2026 TrendMatrix AI Project. All rights reserved.

No license is granted to copy, modify, redistribute, or commercially use this project's original source code without prior written permission, except for permissions provided by applicable platform terms. Third-party libraries, datasets, and services remain subject to their respective licenses and terms.

---

**TrendMatrix AI — Explore Earth. Detect Trends. Understand Change.**
