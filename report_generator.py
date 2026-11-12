
"""
TrendMatrix AI - Scientific Report Generator

This module converts verified statistical analysis results and
dataset metadata into professional, standalone HTML reports.

The report can be generated independently of the Gemini API.
AI-generated explanations are optional and are clearly separated
from Python-calculated statistical results.
"""

import html
import re
from datetime import datetime, timezone
from pathlib import Path


# --------------------------------------------------
# Project paths and report settings
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

REPORT_DIR = BASE_DIR / "data" / "reports"

DEFAULT_P_VALUE_THRESHOLD = 0.05


# --------------------------------------------------
# General helper functions
# --------------------------------------------------

def _get_nested_value(data, *keys, default=None):
    """
    Retrieve a value from a dictionary using multiple possible keys.

    Supports nested dictionary paths.
    """

    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default

        current = current[key]

    return current


def _first_available(data, paths, default=None):
    """
    Return the first available value from a list of dictionary paths.
    """

    for path in paths:
        value = _get_nested_value(data, *path)

        if value is not None:
            return value

    return default


def _format_number(value, decimals=4):
    """
    Format numeric values safely for report display.
    """

    if value is None:
        return "Not available"

    try:
        number = float(value)

        if number != number:
            return "Not available"

        return f"{number:,.{decimals}f}"

    except (TypeError, ValueError):
        return html.escape(str(value))


def _format_p_value(value):
    """
    Format p-values using scientific notation when appropriate.
    """

    if value is None:
        return "Not available"

    try:
        number = float(value)

        if number < 0:
            return "Invalid value"

        if number < 0.0001:
            return f"{number:.2e}"

        return f"{number:.4f}"

    except (TypeError, ValueError):
        return html.escape(str(value))


def _sanitize_filename(value):
    """
    Convert a variable or region name into a safe filename component.
    """

    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value))

    return cleaned.strip("_") or "trendmatrix_report"


def _format_display_name(value):
    """
    Convert identifiers such as soil_moisture into readable labels.
    """

    if value is None:
        return "Not specified"

    return str(value).replace("_", " ").title()


# --------------------------------------------------
# Input validation
# --------------------------------------------------

def _validate_report_inputs(analysis, metadata):
    """
    Validate report input structures.
    """

    if not isinstance(analysis, dict) or not analysis:
        raise ValueError("Analysis must be a non-empty dictionary.")

    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")

    return True


# --------------------------------------------------
# Statistical result extraction
# --------------------------------------------------

def _extract_statistical_results(analysis, metadata):
    """
    Extract verified statistical results using supported field names.

    The function supports both top-level and nested result structures.
    """

    direction = _first_available(
        analysis,
        [
            ("direction",),
            ("interpretation", "direction"),
            ("linear_trend", "direction")
        ],
        default="Not available"
    )

    slope = _first_available(
        analysis,
        [
            ("slope_per_year",),
            ("linear_trend", "slope_per_year"),
            ("linear_trend", "slope")
        ]
    )

    p_value = _first_available(
        analysis,
        [
            ("p_value",),
            ("linear_trend", "p_value")
        ]
    )

    hac_p_value = _first_available(
        analysis,
        [
            ("hac_p_value",),
            ("linear_trend", "hac_p_value")
        ]
    )

    r_squared = _first_available(
        analysis,
        [
            ("r_squared",),
            ("linear_trend", "r_squared")
        ]
    )

    confidence_interval = _first_available(
        analysis,
        [
            ("confidence_interval",),
            ("linear_trend", "confidence_interval"),
            ("linear_trend", "hac_confidence_interval")
        ]
    )

    mann_kendall = analysis.get("mann_kendall", {})

    seasonal_mann_kendall = analysis.get(
        "seasonal_mann_kendall",
        {}
    )

    autocorrelation = analysis.get("autocorrelation", {})

    if not isinstance(mann_kendall, dict):
        mann_kendall = {}

    if not isinstance(seasonal_mann_kendall, dict):
        seasonal_mann_kendall = {}

    if not isinstance(autocorrelation, dict):
        autocorrelation = {}

    return {
        "direction": direction,
        "slope": slope,
        "p_value": p_value,
        "hac_p_value": hac_p_value,
        "r_squared": r_squared,
        "confidence_interval": confidence_interval,
        "mann_kendall": mann_kendall,
        "seasonal_mann_kendall": seasonal_mann_kendall,
        "autocorrelation": autocorrelation,
        "significance": _first_available(
            analysis,
            [
                ("interpretation", "significance"),
                ("significance",)
            ]
        ),
        "warning": _first_available(
            analysis,
            [
                ("interpretation", "warning"),
                ("warning",)
            ]
        ),
        "start_date": metadata.get("start_date"),
        "end_date": metadata.get("end_date"),
        "frequency": metadata.get("frequency", "Not specified"),
        "unit": metadata.get("unit", "Not specified")
    }


# --------------------------------------------------
# Scientific interpretation helpers
# --------------------------------------------------

def _get_significance_label(p_value, threshold=DEFAULT_P_VALUE_THRESHOLD):
    """
    Classify statistical significance without changing the p-value.
    """

    if p_value is None:
        return "Not evaluated"

    try:
        return (
            "Statistically significant"
            if float(p_value) < threshold
            else "Not statistically significant"
        )

    except (TypeError, ValueError):
        return "Not evaluated"


def _get_data_source_note(metadata):
    """
    Explain whether the report uses NASA observations or sample data.
    """

    data_type = str(metadata.get("data_type", "")).lower()

    if data_type == "sample_demo" or metadata.get("is_sample") is True:
        return (
            "This report uses synthetic demonstration data. "
            "These values are not real NASA observations and must "
            "not be interpreted as actual environmental measurements."
        )

    if data_type == "cached_nasa":
        return (
            "This report uses previously retrieved and locally cached "
            "NASA data. The observations were not fetched live during "
            "this analysis session."
        )

    if data_type == "live_nasa":
        return (
            "This report uses data retrieved from a NASA data service. "
            "Refer to the dataset metadata for the specific source "
            "and spatial coverage."
        )

    return (
        "The data source could not be fully classified. "
        "Refer to the dataset metadata before interpreting the results."
    )


def _get_spatial_limitation(metadata):
    """
    Describe spatial coverage limitations.
    """

    spatial_type = str(
        metadata.get("spatial_type", "")
    ).lower()

    if spatial_type == "point":
        return (
            "The dataset represents a point location. Its results "
            "should not be interpreted as a regional spatial average."
        )

    if spatial_type == "regional_average":
        return (
            "The dataset represents a regional average. "
            "Local variations within the region may not be visible."
        )

    return (
        "Spatial coverage information was not supplied. "
        "Avoid assuming that the observations represent an entire region."
    )


# --------------------------------------------------
# HTML report sections
# --------------------------------------------------

def _build_metadata_section(metadata):
    """
    Build the dataset information section.
    """

    fields = [
        ("Variable", _format_display_name(metadata.get("variable"))),
        ("Region", metadata.get("region", "Not specified")),
        ("Unit", metadata.get("unit", "Not specified")),
        ("Frequency", metadata.get("frequency", "Not specified")),
        ("Data Source", metadata.get("source_label", metadata.get("source", "Not specified"))),
        ("Data Type", metadata.get("data_type", "Not specified")),
        ("Start Date", metadata.get("start_date", "Not specified")),
        ("End Date", metadata.get("end_date", "Not specified")),
        ("Observations", metadata.get("observation_count", "Not specified"))
    ]

    rows = ""

    for label, value in fields:
        rows += f"""
        <tr>
            <th>{html.escape(str(label))}</th>
            <td>{html.escape(str(value))}</td>
        </tr>
        """

    return f"""
    <section>
        <h2>1. Dataset Information</h2>
        <table>
            <tbody>{rows}</tbody>
        </table>
    </section>
    """


def _build_statistical_section(results):
    """
    Build the statistical analysis results section.
    """

    mk = results["mann_kendall"]
    seasonal_mk = results["seasonal_mann_kendall"]
    autocorrelation = results["autocorrelation"]

    rows = [
        ("Trend Direction", results["direction"]),
        (
            "Linear Slope per Year",
            _format_number(results["slope"])
        ),
        (
            "Ordinary Linear Regression p-value",
            _format_p_value(results["p_value"])
        ),
        (
            "HAC-adjusted p-value",
            _format_p_value(results["hac_p_value"])
        ),
        (
            "R-squared",
            _format_number(results["r_squared"])
        ),
        (
            "Mann-Kendall Trend",
            mk.get("trend", "Not available")
        ),
        (
            "Mann-Kendall p-value",
            _format_p_value(mk.get("p_value"))
        ),
        (
            "Seasonal Mann-Kendall Trend",
            seasonal_mk.get("trend", "Not available")
        ),
        (
            "Seasonal Mann-Kendall p-value",
            _format_p_value(seasonal_mk.get("p_value"))
        ),
        (
            "Lag-1 Residual Autocorrelation",
            _format_number(autocorrelation.get("lag_1"))
        )
    ]

    table_rows = ""

    for label, value in rows:
        table_rows += f"""
        <tr>
            <th>{html.escape(str(label))}</th>
            <td>{html.escape(str(value))}</td>
        </tr>
        """

    confidence_interval = results["confidence_interval"]

    if isinstance(confidence_interval, (list, tuple)) and len(confidence_interval) >= 2:
        interval_text = (
            f"{_format_number(confidence_interval[0])} "
            f"to {_format_number(confidence_interval[1])}"
        )
    else:
        interval_text = "Not available"

    table_rows += f"""
    <tr>
        <th>Confidence Interval</th>
        <td>{html.escape(interval_text)}</td>
    </tr>
    """

    return f"""
    <section>
        <h2>2. Statistical Analysis Results</h2>
        <table>
            <tbody>{table_rows}</tbody>
        </table>
        <p class="note">
            Statistical significance is interpreted using a default
            p-value threshold of {DEFAULT_P_VALUE_THRESHOLD}.
            Ordinary and HAC-adjusted p-values are reported separately.
        </p>
    </section>
    """


def _build_interpretation_section(results):
    """
    Build a cautious interpretation of the supplied results.
    """

    direction = _format_display_name(results["direction"])

    significance = results["significance"]

    if significance is None:
        significance = _get_significance_label(
            results["hac_p_value"]
            if results["hac_p_value"] is not None
            else results["p_value"]
        )

    slope = results["slope"]

    if slope is not None:
        slope_text = (
            f"The estimated linear rate of change is "
            f"{_format_number(slope)} {html.escape(str(results['unit']))} per year."
        )
    else:
        slope_text = "A linear rate of change was not available."

    warning = results["warning"]

    warning_html = ""

    if warning:
        warning_html = f"""
        <p class="warning">
            <strong>Analysis warning:</strong>
            {html.escape(str(warning))}
        </p>
        """

    return f"""
    <section>
        <h2>3. Trend Interpretation</h2>
        <p>
            The reported trend direction is
            <strong>{html.escape(direction)}</strong>.
        </p>
        <p>{slope_text}</p>
        <p>
            Statistical significance assessment:
            <strong>{html.escape(str(significance))}</strong>.
        </p>
        {warning_html}
        <p>
            Trend magnitude and statistical significance are separate
            properties. A larger slope does not automatically mean
            stronger statistical evidence.
        </p>
    </section>
    """


def _build_limitations_section(metadata):
    """
    Build the data quality and scientific limitations section.
    """

    source_note = _get_data_source_note(metadata)
    spatial_note = _get_spatial_limitation(metadata)

    return f"""
    <section>
        <h2>4. Data Sources and Limitations</h2>
        <ul>
            <li>{html.escape(source_note)}</li>
            <li>{html.escape(spatial_note)}</li>
            <li>
                Statistical trends describe patterns in the supplied
                observations; they do not independently establish
                the physical causes of those patterns.
            </li>
            <li>
                Seasonal cycles, missing observations, data quality,
                and temporal autocorrelation should be considered
                when interpreting long-term trends.
            </li>
        </ul>
    </section>
    """


def _build_ai_section(ai_explanation):
    """
    Include an AI explanation only when a successful response exists.

    AI content is visually separated from verified statistical results.
    """

    if not isinstance(ai_explanation, dict):
        return ""

    if not ai_explanation.get("success"):
        return ""

    explanation = ai_explanation.get("explanation")

    if not explanation:
        return ""

    safe_explanation = html.escape(str(explanation))

    return f"""
    <section>
        <h2>5. AI-Generated Scientific Explanation</h2>
        <p class="note">
            This section contains an AI-generated interpretation.
            It is supplementary and does not replace the verified
            statistical calculations shown above.
        </p>
        <div class="ai-explanation">{safe_explanation}</div>
        <p class="small">
            Provider: {html.escape(str(ai_explanation.get("provider", "Not specified")))}
            |
            Model: {html.escape(str(ai_explanation.get("model", "Not specified")))}
        </p>
    </section>
    """


# --------------------------------------------------
# HTML document generation
# --------------------------------------------------

def _build_html_report(analysis, metadata, ai_explanation=None):
    """
    Assemble the complete standalone HTML scientific report.
    """

    results = _extract_statistical_results(
        analysis=analysis,
        metadata=metadata
    )

    variable = _format_display_name(metadata.get("variable"))
    region = metadata.get("region", "Unspecified Region")

    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    ai_section = _build_ai_section(ai_explanation)

    html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendMatrix AI - Scientific Report</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 35px 18px;
            background: #f3f5f9;
            color: #263247;
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.65;
        }}

        .report {{
            max-width: 950px;
            margin: auto;
            padding: 42px;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 5px 25px rgba(0, 0, 0, 0.07);
        }}

        header {{
            padding-bottom: 24px;
            border-bottom: 2px solid #e5eaf1;
        }}

        h1 {{
            margin: 0;
            color: #173b68;
            font-size: 30px;
        }}

        h2 {{
            margin-top: 32px;
            padding-bottom: 9px;
            color: #24558c;
            border-bottom: 1px solid #e5eaf1;
            font-size: 21px;
        }}

        .subtitle {{
            color: #64748b;
        }}

        table {{
            width: 100%;
            margin-top: 16px;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 11px 13px;
            text-align: left;
            border-bottom: 1px solid #e8edf3;
            overflow-wrap: anywhere;
        }}

        th {{
            width: 42%;
            color: #334155;
            background: #f7f9fc;
        }}

        .note {{
            padding: 13px;
            color: #475569;
            background: #f1f5f9;
            border-left: 4px solid #64748b;
        }}

        .warning {{
            padding: 13px;
            color: #854d0e;
            background: #fef9c3;
            border-left: 4px solid #eab308;
        }}

        .ai-explanation {{
            padding: 18px;
            white-space: pre-wrap;
            background: #f5f3ff;
            border-left: 4px solid #8b5cf6;
            border-radius: 5px;
        }}

        .small {{
            color: #64748b;
            font-size: 13px;
        }}

        footer {{
            margin-top: 38px;
            padding-top: 18px;
            color: #64748b;
            border-top: 1px solid #e5eaf1;
            font-size: 13px;
        }}

        @media print {{
            body {{
                padding: 0;
                background: white;
            }}

            .report {{
                max-width: none;
                padding: 15px;
                box-shadow: none;
            }}

            h2 {{
                break-after: avoid;
            }}

            table, .ai-explanation {{
                break-inside: avoid;
            }}
        }}

        @media (max-width: 600px) {{
            .report {{
                padding: 22px 15px;
            }}

            h1 {{
                font-size: 24px;
            }}

            th, td {{
                padding: 9px;
            }}
        }}
    </style>
</head>

<body>
    <main class="report">

        <header>
            <h1>TrendMatrix AI</h1>
            <h2>Earth Science Trend Analysis Report</h2>

            <p class="subtitle">
                Variable: {html.escape(str(variable))}<br>
                Region: {html.escape(str(region))}
            </p>

            <p class="small">
                Generated: {generated_at}
            </p>
        </header>

        {_build_metadata_section(metadata)}

        {_build_statistical_section(results)}

        {_build_interpretation_section(results)}

        {_build_limitations_section(metadata)}

        {ai_section}

        <footer>
            <strong>TrendMatrix AI</strong><br>
            Earth Systems Trend Analysis Platform<br>
            This report presents supplied statistical results and
            clearly distinguishes them from supplementary AI explanations.
        </footer>

    </main>
</body>
</html>
"""

    return html_document


# --------------------------------------------------
# Public report generation function
# --------------------------------------------------

def generate_report(
    analysis,
    metadata,
    ai_explanation=None,
    output_dir=None
):
    """
    Generate and save a standalone HTML scientific report.

    Args:
        analysis (dict):
            Verified statistical analysis results.

        metadata (dict):
            Dataset information.

        ai_explanation (dict, optional):
            Result returned by ai_explainer.explain_analysis().

        output_dir (str or Path, optional):
            Custom report output directory.

    Returns:
        dict:
            Report generation status and saved file information.
    """

    try:
        _validate_report_inputs(
            analysis=analysis,
            metadata=metadata
        )

        report_html = _build_html_report(
            analysis=analysis,
            metadata=metadata,
            ai_explanation=ai_explanation
        )

        destination = (
            Path(output_dir)
            if output_dir is not None
            else REPORT_DIR
        )

        destination.mkdir(
            parents=True,
            exist_ok=True
        )

        variable = _sanitize_filename(
            metadata.get("variable", "earth_science")
        )

        region = _sanitize_filename(
            metadata.get("region", "region")
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"trendmatrix_{variable}_{region}_{timestamp}.html"
        )

        report_path = destination / filename

        report_path.write_text(
            report_html,
            encoding="utf-8"
        )

        return {
            "success": True,
            "format": "html",
            "filename": filename,
            "file_path": str(report_path.resolve()),
            "message": "Scientific report generated successfully."
        }

    except (TypeError, ValueError, OSError) as error:
        return {
            "success": False,
            "format": None,
            "filename": None,
            "file_path": None,
            "message": "Report generation failed.",
            "error": f"{type(error).__name__}: {error}"
        }


# --------------------------------------------------
# Module testing
# --------------------------------------------------

if __name__ == "__main__":

    print("TRENDMATRIX AI - REPORT GENERATOR TEST")
    print("=" * 48)

    sample_analysis = {
        "direction": "increasing",
        "slope_per_year": 0.3174,
        "p_value": 0.0001,
        "hac_p_value": 0.000018,
        "r_squared": 0.82,
        "confidence_interval": [0.25, 0.38],
        "mann_kendall": {
            "trend": "increasing",
            "p_value": 0.001
        },
        "seasonal_mann_kendall": {
            "trend": "increasing",
            "p_value": 0.002
        },
        "autocorrelation": {
            "lag_1": 0.25
        },
        "interpretation": {
            "direction": "increasing",
            "significance": "Statistically significant",
            "warning": None
        }
    }

    sample_metadata = {
        "variable": "temperature",
        "unit": "°C",
        "region": "Phoenix Test",
        "frequency": "monthly",
        "data_type": "sample_demo",
        "source_label": "Synthetic Demo Data",
        "start_date": "2020-01-01",
        "end_date": "2021-12-01",
        "observation_count": 24,
        "spatial_type": "point"
    }

    # Test 1: Generate a report without Gemini.
    print("\nTEST 1: REPORT GENERATION")
    print("-" * 48)

    result = generate_report(
        analysis=sample_analysis,
        metadata=sample_metadata
    )

    print("Success:", result["success"])
    print("Format:", result["format"])
    print("Filename:", result["filename"])
    print("File path:", result["file_path"])
    print("Message:", result["message"])

    if not result["success"]:
        print("Error:", result.get("error"))

    # Test 2: Confirm the generated file exists.
    print("\nTEST 2: FILE VERIFICATION")
    print("-" * 48)

    file_exists = (
        result["success"]
        and Path(result["file_path"]).is_file()
    )

    print("Report file exists:", file_exists)

    # Test 3: Verify scientific source disclosure.
    print("\nTEST 3: SCIENTIFIC DATA DISCLOSURE")
    print("-" * 48)

    if file_exists:
        saved_html = Path(result["file_path"]).read_text(
            encoding="utf-8"
        )

        disclosure_passed = (
            "Synthetic Demo Data" in saved_html
            and "not real NASA observations" in saved_html
            and "point location" in saved_html
        )
    else:
        disclosure_passed = False

    print(
        "Synthetic data and spatial limitations:",
        "Passed" if disclosure_passed else "Failed"
    )

    # Test 4: Validate invalid input handling.
    print("\nTEST 4: INPUT VALIDATION")
    print("-" * 48)

    invalid_result = generate_report(
        analysis={},
        metadata=sample_metadata
    )

    validation_passed = (
        invalid_result["success"] is False
        and invalid_result.get("error") is not None
    )

    print(
        "Invalid input handling:",
        "Passed" if validation_passed else "Failed"
    )

    # Final test summary.
    all_tests_passed = all([
        result["success"],
        file_exists,
        disclosure_passed,
        validation_passed
    ])

    print("\nTEST SUMMARY")
    print("=" * 48)
    print("Report generation:", "Passed" if result["success"] else "Failed")
    print("File verification:", "Passed" if file_exists else "Failed")
    print("Scientific disclosure:", "Passed" if disclosure_passed else "Failed")
    print("Input validation:", "Passed" if validation_passed else "Failed")

    print(
        "\nReport generator module:",
        "TESTED SUCCESSFULLY" if all_tests_passed else "TEST FAILED"
    )
