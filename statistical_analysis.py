
"""
TrendMatrix AI - Statistical Analysis Engine

This module performs scientific trend analysis on Earth science
time-series data.

Methods:
1. Linear regression
2. Mann-Kendall trend test
3. Sen's slope estimator
4. Seasonal Mann-Kendall test for monthly data
5. Lag-1 residual autocorrelation diagnostic
6. Newey-West HAC robust regression inference

Important:
- Trend magnitude and statistical significance are reported separately.
- Ordinary regression and HAC-adjusted p-values are distinguished.
- Statistical results do not establish causation.
"""

from typing import Any

import numpy as np
import pandas as pd
import pymannkendall as mk

from scipy import stats
from statsmodels.api import OLS, add_constant


class StatisticalAnalysisError(Exception):
    """Raised when statistical analysis cannot be completed."""


DAYS_PER_YEAR = 365.2425
MONTHS_PER_YEAR = 12


def _prepare_series(
    data: pd.Series | pd.DataFrame,
    variable: str | None = None,
) -> pd.Series:
    """Validate and prepare a chronological numeric time series."""

    if isinstance(data, pd.DataFrame):
        if variable is None:
            if data.shape[1] != 1:
                raise ValueError(
                    "Provide a variable name when the DataFrame "
                    "contains multiple columns."
                )
            variable = data.columns[0]

        if variable not in data.columns:
            raise ValueError(
                f"Variable '{variable}' was not found in the DataFrame."
            )

        series = data[variable].copy()

    elif isinstance(data, pd.Series):
        series = data.copy()

        if variable is not None and series.name != variable:
            raise ValueError(
                f"The supplied Series does not represent '{variable}'."
            )

    else:
        raise TypeError(
            "Input must be a pandas Series or DataFrame."
        )

    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError(
            "Time series must use a pandas DatetimeIndex."
        )

    series = pd.to_numeric(series, errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan)
    series = series.dropna().sort_index()

    if series.index.has_duplicates:
        raise ValueError(
            "Duplicate dates found. Aggregate observations before analysis."
        )

    if len(series) < 3:
        raise StatisticalAnalysisError(
            "At least 3 valid observations are required."
        )

    if not np.isfinite(series.to_numpy(dtype=float)).all():
        raise StatisticalAnalysisError(
            "The time series contains invalid numeric values."
        )

    return series.astype(float)


def _detect_frequency(series: pd.Series) -> str:
    """Estimate whether the time series is daily or monthly."""

    if len(series) < 2:
        return "unknown"

    differences = series.index.to_series().diff().dropna()
    median_days = differences.dt.total_seconds().median() / 86400

    if 25 <= median_days <= 35:
        return "monthly"

    if 0.5 <= median_days <= 2:
        return "daily"

    return "irregular"


def _calculate_linear_trend(
    series: pd.Series,
    confidence_level: float,
) -> dict[str, Any]:
    """Calculate linear regression and HAC-adjusted inference."""

    elapsed_years = (
        (series.index - series.index[0]).total_seconds()
        / (86400 * DAYS_PER_YEAR)
    )

    x = np.asarray(elapsed_years, dtype=float)
    y = series.to_numpy(dtype=float)

    regression = stats.linregress(x, y)

    slope = float(regression.slope)
    intercept = float(regression.intercept)
    p_value = float(regression.pvalue)
    r_squared = float(regression.rvalue ** 2)

    residuals = y - (intercept + slope * x)

    degrees_of_freedom = len(y) - 2

    if degrees_of_freedom > 0:
        critical_value = stats.t.ppf(
            (1 + confidence_level) / 2,
            degrees_of_freedom,
        )

        margin = critical_value * regression.stderr

        confidence_interval = [
            float(slope - margin),
            float(slope + margin),
        ]
    else:
        confidence_interval = [None, None]

    # Newey-West HAC covariance provides inference that is more
    # robust to heteroskedasticity and serial correlation.
    hac_maxlags = min(
        max(1, int(len(y) ** (1 / 3))),
        len(y) - 1,
    )

    design_matrix = add_constant(x)

    hac_model = OLS(y, design_matrix).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": hac_maxlags},
    )

    hac_confidence_interval = hac_model.conf_int(
        alpha=1 - confidence_level
    )

    return {
        "slope_per_year": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "p_value": p_value,
        "confidence_interval": confidence_interval,
        "hac_p_value": float(hac_model.pvalues[1]),
        "hac_confidence_interval": [
            float(hac_confidence_interval[1, 0]),
            float(hac_confidence_interval[1, 1]),
        ],
        "hac_maxlags": hac_maxlags,
        "residuals": residuals,
    }


def _calculate_autocorrelation(
    residuals: np.ndarray,
) -> dict[str, Any]:
    """Calculate lag-1 autocorrelation of detrended residuals."""

    if len(residuals) < 4:
        return {
            "lag_1_correlation": None,
            "interpretation": "Insufficient observations.",
        }

    previous = residuals[:-1]
    current = residuals[1:]

    if np.std(previous) == 0 or np.std(current) == 0:
        correlation = None
    else:
        correlation = float(
            np.corrcoef(previous, current)[0, 1]
        )

    if correlation is None:
        interpretation = "Autocorrelation could not be estimated."
    elif abs(correlation) >= 0.5:
        interpretation = (
            "Strong lag-1 residual autocorrelation detected."
        )
    elif abs(correlation) >= 0.2:
        interpretation = (
            "Moderate lag-1 residual autocorrelation detected."
        )
    else:
        interpretation = (
            "Weak lag-1 residual autocorrelation detected."
        )

    return {
        "lag_1_correlation": correlation,
        "interpretation": interpretation,
    }


def _calculate_mann_kendall(
    series: pd.Series,
    frequency: str,
) -> dict[str, Any]:
    """Run the standard Mann-Kendall trend test."""

    values = series.to_numpy(dtype=float)

    result = mk.original_test(values)

    annual_factor = (
        MONTHS_PER_YEAR
        if frequency == "monthly"
        else DAYS_PER_YEAR / 1
    )

    sen_slope = float(result.slope * annual_factor)

    return {
        "trend": str(result.trend),
        "significant": bool(result.h > 0),
        "p_value": float(result.p),
        "z_score": float(result.z),
        "kendall_tau": float(result.Tau),
        "sen_slope_per_year": sen_slope,
    }


def _calculate_seasonal_mann_kendall(
    series: pd.Series,
    frequency: str,
) -> dict[str, Any] | None:
    """Run seasonal Mann-Kendall for sufficiently long monthly data."""

    if frequency != "monthly" or len(series) < 24:
        return None

    try:
        result = mk.seasonal_test(
            series.to_numpy(dtype=float),
            period=12,
        )

        return {
            "trend": str(result.trend),
            "significant": bool(result.h > 0),
            "p_value": float(result.p),
            "z_score": float(result.z),
            "kendall_tau": float(result.Tau),
            "sen_slope_per_month": float(result.slope),
            "sen_slope_per_year": float(result.slope * 12),
            "seasonal_period": 12,
        }

    except Exception as error:
        return {
            "available": False,
            "reason": str(error),
        }


def analyze_trend(
    data: pd.Series | pd.DataFrame,
    variable: str | None = None,
    unit: str = "unknown",
    confidence_level: float = 0.95,
    frequency: str | None = None,
) -> dict[str, Any]:
    """
    Perform comprehensive trend analysis on a time series.

    Args:
        data: A pandas Series or DataFrame with a DatetimeIndex.
        variable: Variable column name when using a DataFrame.
        unit: Measurement unit, such as °C or mm/month.
        confidence_level: Confidence level between 0 and 1.
        frequency: Optional 'daily' or 'monthly' override.

    Returns:
        Dictionary containing trend statistics and diagnostics.
    """

    if not 0 < confidence_level < 1:
        raise ValueError(
            "Confidence level must be between 0 and 1."
        )

    series = _prepare_series(data, variable)

    detected_frequency = _detect_frequency(series)

    if frequency is not None:
        frequency = frequency.lower().strip()

        if frequency not in {"daily", "monthly"}:
            raise ValueError(
                "Frequency must be 'daily' or 'monthly'."
            )

        detected_frequency = frequency

    if detected_frequency == "irregular":
        raise StatisticalAnalysisError(
            "Irregular time intervals detected. "
            "Resample the data to daily or monthly frequency first."
        )

    if detected_frequency == "unknown":
        raise StatisticalAnalysisError(
            "Unable to determine time-series frequency."
        )

    linear = _calculate_linear_trend(
        series,
        confidence_level,
    )

    mann_kendall = _calculate_mann_kendall(
        series,
        detected_frequency,
    )

    seasonal_result = _calculate_seasonal_mann_kendall(
        series,
        detected_frequency,
    )

    autocorrelation = _calculate_autocorrelation(
        linear.pop("residuals")
    )

    
    # Preserve the estimated slope direction separately from
    # the statistically supported Mann-Kendall trend direction.
    if linear["slope_per_year"] > 0:
        estimated_direction = "increasing"
    elif linear["slope_per_year"] < 0:
        estimated_direction = "decreasing"
    else:
        estimated_direction = "no linear change"

    alpha = 1 - confidence_level

    linear_significance = (
        "statistically significant"
        if linear["p_value"] < alpha
        else "not statistically significant"
    )

    hac_significance = (
        "statistically significant"
        if linear["hac_p_value"] < alpha
        else "not statistically significant"
    )

    # Use Mann-Kendall to classify the non-parametric trend.
    # A negative slope alone does not establish a decreasing trend.
    supported_direction = mann_kendall["trend"]

    if supported_direction == "no trend":
        significance = "no statistically significant monotonic trend"
    else:
        significance = "statistically significant monotonic trend"

    return {
        "success": True,
        "variable": variable or series.name or "unknown",
        "unit": unit,
        "frequency": detected_frequency,
        "observation_count": int(len(series)),
        "start_date": series.index.min().strftime("%Y-%m-%d"),
        "end_date": series.index.max().strftime("%Y-%m-%d"),
        "confidence_level": confidence_level,
        "linear_regression": linear,
        "mann_kendall": mann_kendall,
        "seasonal_mann_kendall": seasonal_result,
        "autocorrelation": autocorrelation,
        
        "interpretation": {
            "direction": supported_direction,
            "estimated_linear_direction": estimated_direction,
            "significance": significance,
            "linear_regression_significance": linear_significance,
            "hac_significance": hac_significance,
            "warning": (
                "A negative or positive slope alone does not establish "
                "a statistically significant trend. Ordinary regression "
                "and HAC-adjusted p-values are reported separately. "
                "Mann-Kendall identifies monotonic trend significance. "
                "Review autocorrelation and seasonal diagnostics before "
                "drawing scientific conclusions. Statistical association "
                "does not establish causation."
            ),
        },

    }


if __name__ == "__main__":
    print("TRENDMATRIX AI - STATISTICAL ANALYSIS TEST")
    print("=" * 48)

    dates = pd.date_range(
        start="2015-01-01",
        periods=120,
        freq="MS",
    )

    rng = np.random.default_rng(42)

    test_cases = {
        "Increasing": (
            15 + np.arange(120) * 0.03
            + 2 * np.sin(2 * np.pi * np.arange(120) / 12)
            + rng.normal(0, 0.15, 120)
        ),
        "Decreasing": (
            25 - np.arange(120) * 0.03
            + 2 * np.sin(2 * np.pi * np.arange(120) / 12)
            + rng.normal(0, 0.15, 120)
        ),
        "No trend": (
            20
            + 2 * np.sin(2 * np.pi * np.arange(120) / 12)
            + rng.normal(0, 0.3, 120)
        ),
    }

    for case_name, values in test_cases.items():
        print(f"\nTesting {case_name} dataset...")

        test_series = pd.Series(
            values,
            index=dates,
            name="temperature",
        )

        result = analyze_trend(
            test_series,
            unit="°C",
        )

        print("Direction:", result["interpretation"]["direction"])
        print(
            "Linear slope per year:",
            round(
                result["linear_regression"]["slope_per_year"],
                4,
            ),
        )
        print(
            "Linear p-value:",
            round(
                result["linear_regression"]["p_value"],
                6,
            ),
        )
        print(
            "HAC-adjusted p-value:",
            round(
                result["linear_regression"]["hac_p_value"],
                6,
            ),
        )
        print(
            "Mann-Kendall:",
            result["mann_kendall"]["trend"],
        )
        print(
            "Seasonal Mann-Kendall:",
            result["seasonal_mann_kendall"]["trend"],
        )

    print("\nStatistical analysis module tested successfully.")
