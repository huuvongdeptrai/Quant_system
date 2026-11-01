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

def test_analysis_engine_cache_hit_when_fresh():
    import time
    engine = AnalysisEngine(model_name="gemini-1.5-flash", cache_ttl_seconds=3600.0)
    engine.client = Mock()
    cached_result = {
        "trend_macro": "BULLISH",
        "trend_intraday": "BULLISH",
        "scenario_a": "Buy dips",
        "scenario_b": "Cut below support",
    }
    engine.cache["XAUUSD"] = {
        "timestamp": time.time() - 300,  # 5 minutes old (< 3600s TTL)
        "result": cached_result,
        "support": 1980.0,
        "resistance": 2020.0,
    }
    tech_data = {
        "current_price": 2000.0,  # in range [1980, 2020]
        "resistance": 2020.0,
        "support": 1980.0,
    }
    result = engine.analyze("XAUUSD", force_refresh=False, tech_data=tech_data)
    assert result == cached_result
    engine.client.chat.completions.create.assert_not_called()


def test_analysis_engine_cache_invalidated_when_expired():
    import time
    engine = AnalysisEngine(model_name="gemini-1.5-flash", cache_ttl_seconds=3600.0)
    fresh_response = Mock()
    fresh_response.choices = [
        Mock(message=Mock(content='{"trend_macro": "SIDEWAYS", "trend_intraday": "BEARISH", "scenario_a": "Fresh A", "scenario_b": "Fresh B"}'))
    ]
    engine.client = Mock()
    engine.client.chat.completions.create.return_value = fresh_response

    stale_result = {
        "trend_macro": "BULLISH",
        "trend_intraday": "BULLISH",
        "scenario_a": "Stale A",
        "scenario_b": "Stale B",
    }
    stale_ts = time.time() - 4000  # 4000s old (> 3600s TTL)
    engine.cache["XAUUSD"] = {
        "timestamp": stale_ts,
        "result": stale_result,
        "support": 1980.0,
        "resistance": 2020.0,
    }
    tech_data = {
        "current_price": 2000.0,  # still in range [1980, 2020]
        "resistance": 2020.0,
        "support": 1980.0,
        "ema_50": 1995.0,
        "ema_position": "ABOVE",
        "structure": "BULLISH",
        "math_trend": "BULLISH",
        "session": "London Session",
    }
    result = engine.analyze("XAUUSD", force_refresh=False, tech_data=tech_data)
    assert result["trend_macro"] == "SIDEWAYS"
    assert result["scenario_a"] == "Fresh A"
    engine.client.chat.completions.create.assert_called_once()
    assert engine.cache["XAUUSD"]["timestamp"] > stale_ts
