
"""
TrendMatrix AI - Gemini AI Explanation Module

This module generates natural-language explanations of verified
statistical analysis results using Google's Gemini API.

Important:
- Statistical calculations are performed by Python modules.
- Gemini only explains the verified results.
- Offline fallback is provided when Gemini is unavailable.
- API credentials are loaded from config.py / environment variables.
"""

import json
import os

from google import genai
from google.genai import types

from config import Config


# --------------------------------------------------
# Configuration helpers
# --------------------------------------------------

def _get_default_api_key():
    """
    Retrieve the Gemini API key from application configuration
    or environment variables.
    """

    api_key = getattr(Config, "GEMINI_API_KEY", None)

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "")

    return api_key.strip() if api_key else ""


def _get_default_model():
    """
    Retrieve the configured Gemini model.
    """

    model = getattr(Config, "GEMINI_MODEL", None)

    if not model:
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    return model.strip()


# --------------------------------------------------
# Input validation
# --------------------------------------------------

def _validate_inputs(analysis, metadata):
    """
    Validate statistical analysis and dataset metadata.

    Gemini must receive verified statistical results rather
    than raw or incomplete analysis objects.
    """

    if not isinstance(analysis, dict):
        raise ValueError("Analysis must be a dictionary.")

    if not analysis:
        raise ValueError("Analysis dictionary cannot be empty.")

    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")

    return True


# --------------------------------------------------
# Prompt generation
# --------------------------------------------------

def _build_prompt(analysis, metadata):
    """
    Build a scientific explanation prompt for Gemini.

    Gemini is instructed to explain existing results only.
    It must not invent statistical values or calculations.
    """

    analysis_json = json.dumps(
        analysis,
        indent=2,
        default=str
    )

    metadata_json = json.dumps(
        metadata,
        indent=2,
        default=str
    )

    prompt = f"""
You are an Earth science and climate data interpretation assistant
working inside TrendMatrix AI.

Your task is to explain verified statistical analysis results
in clear, scientifically responsible language.

DATASET METADATA:
{metadata_json}

VERIFIED STATISTICAL RESULTS:
{analysis_json}

INSTRUCTIONS:

1. Explain the detected trend direction.
2. Explain the calculated rate of change and its unit.
3. Interpret statistical significance using the provided p-values.
4. Explain the Mann-Kendall test result if available.
5. Explain autocorrelation information if available.
6. Discuss the possible Earth science implications carefully.
7. Clearly distinguish statistical observations from hypotheses.
8. Do not invent values, measurements, p-values, or conclusions.
9. Do not perform new statistical calculations.
10. Do not claim that correlation proves causation.
11. Mention relevant limitations of the available dataset.
12. If the dataset is synthetic demonstration data, explicitly
    state that it is not real NASA observational data.
13. If the dataset represents a point location, do not describe
    it as a regional spatial average.

Use the following response structure:

### 1. Overview
Briefly describe the dataset and analysis.

### 2. Observed Trend
Explain the trend direction and rate of change.

### 3. Statistical Significance
Interpret the available statistical tests.

### 4. Earth Science Interpretation
Discuss possible scientific implications without claiming
unverified causes.

### 5. Limitations
Mention relevant data and statistical limitations.

### 6. Conclusion
Provide a short, balanced conclusion.

Use professional but understandable English.
"""

    return prompt


# --------------------------------------------------
# Offline fallback
# --------------------------------------------------

def _offline_response(error_message=None):
    """
    Return a safe response when Gemini is unavailable.

    Verified statistical results remain available independently
    through the Python statistical analysis module.
    """

    explanation = (
        "AI explanation is currently unavailable. "
        "The verified statistical analysis is still available "
        "from the Python analysis module. "
        "Please check your internet connection and Gemini API configuration."
    )

    return {
        "success": False,
        "offline_mode": True,
        "provider": None,
        "model": None,
        "explanation": explanation,
        "error": error_message
    }


# --------------------------------------------------
# AI explanation service
# --------------------------------------------------

def explain_analysis(analysis, metadata, api_key=None):
    """
    Generate an explanation of verified statistical results.

    Args:
        analysis (dict):
            Results produced by statistical_analysis.py.

        metadata (dict):
            Dataset metadata such as variable, region, unit,
            source, frequency, and data type.

        api_key (str, optional):
            Explicit API key override.
            If omitted, the configured API key is used.
            An explicitly empty string forces offline mode.

    Returns:
        dict:
            Explanation result, provider information,
            offline status, and error details.
    """

    # Validate input before making an API request.
    try:
        _validate_inputs(analysis, metadata)

    except (TypeError, ValueError) as error:
        return {
            "success": False,
            "offline_mode": False,
            "provider": None,
            "model": None,
            "explanation": None,
            "error": str(error)
        }

    # Use configured key unless an explicit override is supplied.
    if api_key is None:
        api_key = _get_default_api_key()

    if not api_key:
        return _offline_response(
            "Gemini API key is missing."
        )

    model = _get_default_model()

    if not model:
        return _offline_response(
            "Gemini model configuration is missing."
        )

    try:
        # Initialize the Google Gemini client.
        client = genai.Client(api_key=api_key)

        # Generate the scientific explanation.
        prompt = _build_prompt(
            analysis=analysis,
            metadata=metadata
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1200
            )
        )

        explanation = response.text

        if not explanation or not explanation.strip():
            return _offline_response(
                "Gemini returned an empty response."
            )

        return {
            "success": True,
            "offline_mode": False,
            "provider": "Gemini",
            "model": model,
            "explanation": explanation.strip(),
            "error": None
        }

    except Exception as error:
        # Do not expose the API key in error messages.
        return _offline_response(
            f"{type(error).__name__}: {str(error)}"
        )


# --------------------------------------------------
# Module testing
# --------------------------------------------------

if __name__ == "__main__":

    print("TRENDMATRIX AI - AI EXPLAINER TEST")
    print("=" * 45)

    # Sample verified statistical analysis for testing.
    sample_analysis = {
        "direction": "increasing",
        "slope_per_year": 0.3174,
        "p_value": 0.0001,
        "hac_p_value": 0.000018,
        "r_squared": 0.82,
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
        }
    }

    sample_metadata = {
        "variable": "temperature",
        "unit": "°C",
        "region": "Phoenix Test",
        "frequency": "monthly",
        "data_type": "sample_demo",
        "source_label": "Synthetic Demo Data"
    }

    # --------------------------------------------------
    # Test 1: Actual Gemini connection
    # --------------------------------------------------

    print("\nTEST 1: GEMINI API CONNECTION")
    print("-" * 45)

    result = explain_analysis(
        analysis=sample_analysis,
        metadata=sample_metadata
    )

    print("Success:", result["success"])
    print("Offline mode:", result["offline_mode"])
    print("Provider:", result["provider"])
    print("Model:", result["model"])

    if result["success"]:
        print("\nGemini Explanation:")
        print("-" * 45)
        print(result["explanation"])
    else:
        print("Explanation:", result["explanation"])
        print("Error:", result["error"])

    # --------------------------------------------------
    # Test 2: Offline fallback
    # --------------------------------------------------

    print("\nTEST 2: OFFLINE FALLBACK")
    print("-" * 45)

    offline_result = explain_analysis(
        analysis=sample_analysis,
        metadata=sample_metadata,
        api_key=""
    )

    print("Success:", offline_result["success"])
    print("Offline mode:", offline_result["offline_mode"])
    print("Expected offline fallback:", offline_result["offline_mode"])

    # --------------------------------------------------
    # Test 3: Input validation
    # --------------------------------------------------

    print("\nTEST 3: INPUT VALIDATION")
    print("-" * 45)

    validation_result = explain_analysis(
        analysis={},
        metadata=sample_metadata
    )

    validation_passed = (
        validation_result["success"] is False
        and validation_result["error"] is not None
    )

    print("Input validation:", "Passed" if validation_passed else "Failed")

    # --------------------------------------------------
    # Final test summary
    # --------------------------------------------------

    offline_test_passed = (
        offline_result["success"] is False
        and offline_result["offline_mode"] is True
    )

    print("\nTEST SUMMARY")
    print("=" * 45)
    print("Offline fallback:", "Passed" if offline_test_passed else "Failed")
    print("Input validation:", "Passed" if validation_passed else "Failed")

    if result["success"]:
        print("Gemini online connection: Passed")
    else:
        print("Gemini online connection: Not verified")

    if offline_test_passed and validation_passed:
        print("\nAI explanation module tests completed.")
    else:
        print("\nSome module tests failed.")
