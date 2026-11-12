
"""
TrendMatrix AI - Visualization Module

Creates interactive Plotly visualizations for Earth science
time-series datasets.

Responsibilities:
- Display processed observations over time.
- Show optional pre-calculated trend values.
- Preserve dataset metadata in chart labels.
- Export charts as standalone HTML files.

Statistical calculations are handled by statistical_analysis.py.
This module focuses only on visualization.
"""

from pathlib import Path
from typing import Optional, Union

import pandas as pd
import plotly.graph_objects as go


def _prepare_chart_data(
    dataframe: pd.DataFrame,
    variable: str
) -> pd.DataFrame:
    """
    Validate and prepare a DataFrame for time-series visualization.

    The function accepts either a DatetimeIndex or a column named 'date'.
    It does not interpolate or otherwise modify missing observations.
    """

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if dataframe.empty:
        raise ValueError("Cannot visualize an empty dataset.")

    chart_data = dataframe.copy()

    # Use the date column as the index when one is available.
    if "date" in chart_data.columns:
        chart_data["date"] = pd.to_datetime(
            chart_data["date"],
            errors="coerce"
        )
        chart_data = chart_data.set_index("date")

    # Ensure the index contains valid dates.
    chart_data.index = pd.to_datetime(
        chart_data.index,
        errors="coerce"
    )

    chart_data = chart_data.loc[
        chart_data.index.notna()
    ].copy()

    if variable not in chart_data.columns:
        raise ValueError(
            f"Variable '{variable}' was not found in the dataset."
        )

    # Convert observations to numeric values.
    chart_data[variable] = pd.to_numeric(
        chart_data[variable],
        errors="coerce"
    )

    chart_data = chart_data.sort_index()

    if chart_data.empty:
        raise ValueError("No valid dates are available for visualization.")

    if chart_data[variable].notna().sum() == 0:
        raise ValueError(
            f"Variable '{variable}' contains no valid numeric observations."
        )

    return chart_data


def create_time_series_chart(
    dataframe: pd.DataFrame,
    variable: str,
    title: Optional[str] = None,
    unit: Optional[str] = None,
    source_label: Optional[str] = None,
    trend_values: Optional[Union[pd.Series, list]] = None
) -> go.Figure:
    """
    Create an interactive time-series chart.

    Args:
        dataframe:
            Processed observations with a date index or date column.

        variable:
            Name of the Earth science variable to visualize.

        title:
            Optional chart title.

        unit:
            Optional measurement unit. Dataset metadata is used
            when this argument is not provided.

        source_label:
            Optional data source label. Dataset metadata is used
            when this argument is not provided.

        trend_values:
            Optional pre-calculated trend values aligned with
            the observations. This module does not calculate trends.

    Returns:
        A Plotly Figure object.
    """

    chart_data = _prepare_chart_data(dataframe, variable)

    # Read metadata preserved by the data processing modules.
    metadata = dataframe.attrs

    selected_unit = (
        unit
        or metadata.get("unit")
        or metadata.get("units")
        or "Not specified"
    )

    selected_source = (
        source_label
        or metadata.get("source_label")
        or metadata.get("source")
        or "Unknown source"
    )

    frequency = metadata.get("frequency", "Unknown frequency")
    data_type = metadata.get("data_type", "Unknown data type")

    chart_title = title or (
        f"{variable.replace('_', ' ').title()} Over Time"
    )

    figure = go.Figure()

    # Add the original observations.
    figure.add_trace(
        go.Scatter(
            x=chart_data.index,
            y=chart_data[variable],
            mode="lines+markers",
            name="Observed Data",
            connectgaps=False,
            line=dict(width=2),
            marker=dict(size=5),
            hovertemplate=(
                "Date: %{x|%Y-%m-%d}<br>"
                f"{variable.replace('_', ' ').title()}: "
                "%{y:.3f}<br>"
                "<extra></extra>"
            )
        )
    )

    # Display an optional trend calculated by the analysis module.
    if trend_values is not None:

        trend_series = pd.Series(trend_values)

        if len(trend_series) != len(chart_data):
            raise ValueError(
                "trend_values must have the same number of "
                "observations as the chart dataset."
            )

        figure.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=trend_series.values,
                mode="lines",
                name="Calculated Trend",
                line=dict(
                    dash="dash",
                    width=2
                ),
                hovertemplate=(
                    "Date: %{x|%Y-%m-%d}<br>"
                    "Trend: %{y:.3f}<br>"
                    "<extra></extra>"
                )
            )
        )

    figure.update_layout(
        title={
            "text": chart_title,
            "x": 0.5,
            "xanchor": "center"
        },
        xaxis_title="Date",
        yaxis_title=f"{variable.replace('_', ' ').title()} ({selected_unit})",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(
            l=60,
            r=30,
            t=90,
            b=60
        ),
        annotations=[
            dict(
                text=(
                    f"Source: {selected_source} | "
                    f"Frequency: {frequency} | "
                    f"Data type: {data_type}"
                ),
                xref="paper",
                yref="paper",
                x=0,
                y=-0.22,
                showarrow=False,
                align="left",
                font=dict(size=10, color="gray")
            )
        ]
    )

    figure.update_xaxes(
        showgrid=True,
        rangeslider_visible=True
    )

    figure.update_yaxes(
        showgrid=True,
        zeroline=True
    )

    return figure


def save_chart_html(
    figure: go.Figure,
    output_path: Union[str, Path]
) -> Path:
    """
    Save a Plotly chart as a standalone HTML file.

    The generated file can be opened in a web browser.
    """

    if not isinstance(figure, go.Figure):
        raise TypeError("Expected a Plotly Figure object.")

    output_path = Path(output_path)

    if output_path.suffix.lower() != ".html":
        raise ValueError("Chart output path must end with .html.")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    figure.write_html(
        str(output_path),
        include_plotlyjs=True,
        full_html=True
    )

    return output_path


if __name__ == "__main__":

    # Create a small synthetic dataset for module testing.
    sample_dates = pd.date_range(
        start="2020-01-01",
        periods=24,
        freq="MS"
    )

    sample_data = pd.DataFrame(
        {
            "temperature": [
                18.2, 19.1, 20.4, 22.0, 24.1, 26.5,
                28.0, 27.6, 25.2, 22.8, 20.1, 18.7,
                18.5, 19.4, 20.8, 22.5, 24.6, 27.0,
                28.5, 28.1, 25.8, 23.2, 20.5, 19.0
            ]
        },
        index=sample_dates
    )

    sample_data.attrs["source_label"] = "Synthetic Demo Data"
    sample_data.attrs["data_type"] = "sample_demo"
    sample_data.attrs["frequency"] = "monthly"
    sample_data.attrs["unit"] = "°C"

    # Create the chart.
    chart = create_time_series_chart(
        dataframe=sample_data,
        variable="temperature"
    )

    # Export the chart for verification.
    output_file = save_chart_html(
        chart,
        Path("data") / "test_temperature_chart.html"
    )

    print("TRENDMATRIX AI - VISUALIZATION TEST")
    print("=" * 45)
    print("Chart created successfully.")
    print(f"Variable: temperature")
    print(f"Observations: {len(sample_data)}")
    print(f"Data source: {sample_data.attrs['source_label']}")
    print(f"Output file: {output_file.resolve()}")
    print("Visualization module tested successfully.")

