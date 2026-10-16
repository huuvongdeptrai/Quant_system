# -*- coding: utf-8 -*-
"""
Quant AI V2.2 - Dynamic Strategy Loader & User Strategy Registry
Provides dynamic auto-discovery, AST validation, and runtime import for:
1. Built-in Quantitative Strategies (backend/core/strategies/)
2. User-Created Custom Strategies (Documents/Quant_AI/Strategies/)
"""

import os
import sys
import ast
import shutil
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from loguru import logger


def get_user_strategies_dir() -> Path:
    """Returns the user strategies directory in Documents/Quant_AI/Strategies/."""
    user_docs = Path(os.path.expanduser("~")) / "Documents" / "Quant_AI" / "Strategies"
    user_docs.mkdir(parents=True, exist_ok=True)

    # Seed an example template file if directory is empty
    example_file = user_docs / "custom_ict_fvg.py"
    if not example_file.exists() and len(list(user_docs.glob("*.py"))) == 0:
        example_content = '''# -*- coding: utf-8 -*-
"""
Custom User Strategy Example: ICT Fair Value Gap (FVG) Sniper
Quant AI V2.2 Template
"""

import pandas as pd
from typing import Dict, Any

class CustomICTFVGStrategy:
    """ICT FVG Breakout & Retest Model."""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "Custom ICT FVG Sniper"
        self.rr_ratio = self.config.get("rr_ratio", 2.5)

    def analyze(self, df: pd.DataFrame, macro_context: Dict = None) -> Dict[str, Any]:
        """
        Input: OHLCV DataFrame
        Output: Signal dict with 'strategy', 'signal' ('BUY'/'SELL'/'HOLD'), 'confidence', 'sl_price', 'tp_price'
        """
        if df is None or len(df) < 30:
            return {"strategy": self.name, "signal": "HOLD", "confidence": 0.0}

        close = df["close"].iloc[-1]
        c_prev = df["close"].iloc[-2]
        c_prev2 = df["close"].iloc[-3]
        high_prev2 = df["high"].iloc[-3]
        low_prev = df["low"].iloc[-1]

        signal = "HOLD"
        confidence = 0.0

        # Bullish FVG condition: low[-1] > high[-3]
        if low_prev > high_prev2 and c_prev > high_prev2:
            signal = "BUY"
            confidence = 0.82
            sl = float(df["low"].iloc[-3])
            tp = float(close + (close - sl) * self.rr_ratio)
            return {
                "strategy": self.name,
                "signal": signal,
                "entry_price": float(close),
                "confidence": confidence,
                "sl_price": sl,
                "tp_price": tp,
            }

        return {"strategy": self.name, "signal": "HOLD", "confidence": 0.0}
'''
        try:
            with open(example_file, "w", encoding="utf-8") as f:
                f.write(example_content)
        except Exception as e:
            logger.warning(f"Failed to seed example strategy: {e}")

    return user_docs


def validate_strategy_file(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates a Python strategy file using AST parsing and interface check.
    Returns: (is_valid, message, class_name)
    """
    p = Path(file_path)
    if not p.exists() or p.suffix.lower() != ".py":
        return False, "File does not exist or is not a .py script", None

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()

        tree = ast.parse(code, filename=p.name)
    except SyntaxError as e:
        return False, f"Syntax Error at line {e.lineno}: {e.msg}", None
    except Exception as e:
        return False, f"Parse error: {e}", None

    target_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            # Check if class has an 'analyze' method
            for subnode in node.body:
                if isinstance(subnode, ast.FunctionDef) and subnode.name == "analyze":
                    target_class = node.name
                    break
            if target_class:
                break

    if not target_class:
        return False, "No class with an 'analyze(df, ...)' method found in file", None

    return True, "Valid Strategy", target_class


def import_strategy_file(source_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates and copies a strategy file into the user strategies directory.
    Returns: (success, message, strategy_info)
    """
    valid, msg, class_name = validate_strategy_file(source_path)
    if not valid:
        return False, msg, None

    user_dir = get_user_strategies_dir()
    src = Path(source_path)
    dst = user_dir / src.name

    try:
        shutil.copy2(src, dst)
        strat_info = {
            "id": f"user_{dst.stem}",
            "name": f"{class_name} (User)",
            "file_name": dst.name,
            "file_path": str(dst),
            "class_name": class_name,
            "is_builtin": False,
        }
        return True, f"Imported successfully: {dst.name}", strat_info
    except Exception as e:
        return False, f"Copy error: {e}", None


def discover_strategies() -> List[Dict[str, Any]]:
    """
    Scans and returns all available built-in and user strategies.
    """
    strategies: List[Dict[str, Any]] = [
        {
            "id": "builtin_ict_pro",
            "name": "ICT Zones Pro v4.2 (Asian Sweep + FVG)",
            "file_name": "ict_strategy.py",
            "file_path": str(Path(__file__).parent / "ict_strategy.py"),
            "class_name": "ICTZonesProStrategy",
            "is_builtin": True,
            "description": "Asian High/Low sweep, Judas swing, Fair Value Gap and Killzone filter."
        },
        {
            "id": "builtin_wyckoff",
            "name": "Wyckoff Momentum Pro (Vectorized)",
            "file_name": "backtest_vectorized.py",
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "research" / "backtest_vectorized.py"),
            "class_name": "VectorizedBacktester",
            "is_builtin": True,
            "description": "Vectorized NumPy ATR envelope and Volume expansion momentum model."
        },
        {
            "id": "builtin_ema_stress",
            "name": "EMA Dual Cross (Resilience Benchmark)",
            "file_name": "ema_stress_test.py",
            "file_path": str(Path(__file__).parent / "ema_stress_test.py"),
            "class_name": "EMAStressTestStrategy",
            "is_builtin": True,
            "description": "Fast EMA10 / Slow EMA50 crossover with dynamic risk sizing."
        },
    ]

    # Scan User Strategies folder
    user_dir = get_user_strategies_dir()
    for py_file in user_dir.glob("*.py"):
        valid, _, class_name = validate_strategy_file(str(py_file))
        if valid and class_name:
            strategies.append({
                "id": f"user_{py_file.stem}",
                "name": f"{class_name} (Custom)",
                "file_name": py_file.name,
                "file_path": str(py_file),
                "class_name": class_name,
                "is_builtin": False,
                "description": f"User strategy loaded from {py_file.name}"
            })

    return strategies


def load_strategy_instance(file_path: str, class_name: str, config: Optional[Dict] = None) -> Optional[Any]:
    """
    Dynamically loads and instantiates a strategy class at runtime.
    """
    p = Path(file_path)
    if not p.exists():
        logger.error(f"Strategy file not found: {file_path}")
        return None

    try:
        mod_name = f"dynamic_strat_{p.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, str(p))
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)

        cls = getattr(module, class_name, None)
        if cls:
            return cls(config or {})
        logger.error(f"Class '{class_name}' not found in module '{mod_name}'")
        return None
    except Exception as e:
        logger.error(f"Failed to load strategy instance from {file_path}: {e}")
        return None
