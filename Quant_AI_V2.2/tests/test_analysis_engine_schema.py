import pytest
from unittest.mock import Mock, patch
from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine


def test_analysis_engine_schema_valid():
    raw_data = {
        "trend_macro": "bullish",
        "trend_intraday": "bearish",
        "scenario_a": "Institutional buy on dip.",
        "scenario_b": "Breakdown below support.",
    }
    validated = AnalysisEngine.validate_schema(raw_data)
    assert validated["trend_macro"] == "BULLISH"
    assert validated["trend_intraday"] == "BEARISH"
    assert validated["scenario_a"] == "Institutional buy on dip."
    assert validated["scenario_b"] == "Breakdown below support."


def test_analysis_engine_schema_not_a_dict():
    for invalid in [None, [], "just a string", 123]:
        with pytest.raises(ValueError, match="must be a JSON object"):
            AnalysisEngine.validate_schema(invalid)


def test_analysis_engine_schema_missing_keys():
    incomplete = {
        "trend_macro": "BULLISH",
        "trend_intraday": "SIDEWAYS",
        "scenario_a": "Scenario A",
        # missing scenario_b
    }
    with pytest.raises(ValueError, match="missing required schema key: 'scenario_b'"):
        AnalysisEngine.validate_schema(incomplete)


def test_analysis_engine_schema_empty_string():
    empty_field = {
        "trend_macro": "BULLISH",
        "trend_intraday": "   ",
        "scenario_a": "Scenario A",
        "scenario_b": "Scenario B",
    }
    with pytest.raises(ValueError, match="must be a non-empty string"):
        AnalysisEngine.validate_schema(empty_field)


def test_analysis_engine_schema_invalid_enum():
    invalid_trend = {
        "trend_macro": "UPTREND",  # Invalid enum value
        "trend_intraday": "BEARISH",
        "scenario_a": "Scenario A",
        "scenario_b": "Scenario B",
    }
    with pytest.raises(ValueError, match="Invalid trend_macro value: 'UPTREND'"):
        AnalysisEngine.validate_schema(invalid_trend)


def test_analysis_engine_analyze_catches_invalid_schema():
    engine = AnalysisEngine(model_name="gemini-1.5-flash")
    fake_response = Mock()
    fake_response.choices = [
        Mock(message=Mock(content='{"trend_macro": "INVALID_STATE", "trend_intraday": "BEARISH", "scenario_a": "A", "scenario_b": "B"}'))
    ]
    engine.client = Mock()
    engine.client.chat.completions.create.return_value = fake_response

    tech_data = {
        "current_price": 2000.0,
        "resistance": 2020.0,
        "support": 1980.0,
        "ema_50": 1995.0,
        "ema_position": "ABOVE",
        "structure": "BULLISH",
        "math_trend": "BULLISH",
        "session": "London Session",
    }

    result = engine.analyze("XAUUSD", force_refresh=True, tech_data=tech_data)
    assert "error" in result
    assert "Invalid trend_macro value" in result["error"]
    assert "XAUUSD" not in engine.cache
