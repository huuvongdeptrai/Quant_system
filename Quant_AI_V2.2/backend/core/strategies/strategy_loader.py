# -*- coding: utf-8 -*-
"""
Quant AI V2.2 - Centralized Strategy Loader & Registry (Domain Layer)
All quantitative strategies reside in 'backend/core/strategies/':
1. Built-in Core Strategies (ict_strategy.py, wyckoff_vectorized.py, ema_stress_test.py)
2. Custom User Strategies (custom_ict_fvg.py and any .py file placed in backend/core/strategies/)
"""

import os
import sys
import ast
import shutil
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from loguru import logger


def get_strategies_dir() -> Path:
    """Returns the centralized top-level strategies directory in the project."""
    strat_dir = Path(__file__).resolve().parent
    strat_dir.mkdir(parents=True, exist_ok=True)
    return strat_dir


def get_user_strategies_dir() -> Path:
    """
    Returns the primary strategies directory.
    Users can place custom strategies directly into 'strategies/' at the project root.
    """
    return get_strategies_dir()


def validate_strategy_file(file_path: str, is_builtin: bool = False) -> Tuple[bool, str, Optional[str]]:
    """
    Validates a Python strategy file using AST parsing, interface check,
    and enforces AST Security Sandbox on custom strategies.
    Returns: (is_valid, message, class_name)
    """
    p = Path(file_path)
    if not p.exists() or p.suffix.lower() != ".py":
        return False, "File does not exist or is not a .py script", None

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()

        # AST Sandbox Security Guard: Enforce strict safety on all non-builtin strategies
        if not is_builtin:
            from backend.core.security_guard import validate_strategy_code
            is_safe, violation = validate_strategy_code(code)
            if not is_safe:
                return False, f"Bảo mật từ chối (AST Sandbox Guard): {violation}", None

        tree = ast.parse(code, filename=p.name)
    except SyntaxError as e:
        return False, f"Syntax Error at line {e.lineno}: {e.msg}", None
    except Exception as e:
        return False, f"Parse error: {e}", None

    target_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            # Check if class has an 'analyze' or 'run' method
            for subnode in node.body:
                if isinstance(subnode, ast.FunctionDef) and subnode.name in ("analyze", "run"):
                    target_class = node.name
                    break
            if target_class:
                break

    if not target_class:
        return False, "No class with an 'analyze(df, ...)' or 'run(df, ...)' method found in file", None

    return True, "Valid Strategy", target_class


def import_strategy_file(source_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates and copies a strategy file into the centralized strategies/ directory.
    Returns: (success, message, strategy_info)
    """
    valid, msg, class_name = validate_strategy_file(source_path)
    if not valid:
        return False, msg, None

    dest_dir = get_strategies_dir()
    src = Path(source_path)
    dst = dest_dir / src.name

    try:
        shutil.copy2(src, dst)
        strat_info = {
            "id": f"strat_{dst.stem}",
            "name": f"{class_name} (Custom)",
            "file_name": dst.name,
            "file_path": str(dst),
            "class_name": class_name,
            "is_builtin": False,
        }
        return True, f"Imported successfully into backend/core/strategies/{dst.name}", strat_info
    except Exception as e:
        return False, f"Copy error: {e}", None


def delete_strategy_file(strategy_id_or_file_path: str) -> Tuple[bool, str]:
    """
    Safely archives/removes a custom strategy file.
    Protected built-in strategies (ict_strategy.py, wyckoff_vectorized.py, ema_stress_test.py) cannot be deleted.
    Custom strategies are moved to 'backend/core/strategies/archive/' for safety.
    """
    strat_dir = get_strategies_dir()
    protected_files = {
        "ict_strategy.py",
        "wyckoff_vectorized.py",
        "ema_stress_test.py",
        "__init__.py",
        "strategy_loader.py",
        "base_strategy.py",
    }

    # Resolve target file path
    target_path = None
    p_cand = Path(strategy_id_or_file_path)
    if p_cand.exists() and p_cand.is_file():
        target_path = p_cand
    else:
        # Search by id or stem
        for py_file in strat_dir.glob("*.py"):
            if (
                py_file.stem == strategy_id_or_file_path
                or f"strat_{py_file.stem}" == strategy_id_or_file_path
                or py_file.name == strategy_id_or_file_path
            ):
                target_path = py_file
                break

    if not target_path or not target_path.exists():
        return False, f"Strategy file not found: {strategy_id_or_file_path}"

    if target_path.name in protected_files:
        return False, f"Cannot delete protected core strategy: {target_path.name}"

    archive_dir = strat_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dst_archive = archive_dir / target_path.name

    if dst_archive.exists():
        import time
        dst_archive = archive_dir / f"{target_path.stem}_{int(time.time())}{target_path.suffix}"

    try:
        shutil.move(str(target_path), str(dst_archive))
        return True, f"Strategy '{target_path.name}' archived to strategies/archive/"
    except Exception as e:
        return False, f"Failed to archive strategy file: {e}"


def create_template_strategy(target_name: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Generates a production-ready template strategy scaffold inheriting BaseStrategy.
    Returns: (success, message, created_file_path)
    """
    strat_dir = get_strategies_dir()
    name_clean = (target_name or "custom_strategy").lower().replace(" ", "_")
    if not name_clean.endswith(".py"):
        name_clean += ".py"

    file_path = strat_dir / name_clean
    if file_path.exists():
        import time
        name_clean = f"{Path(name_clean).stem}_{int(time.time())}.py"
        file_path = strat_dir / name_clean

    template_code = '''# -*- coding: utf-8 -*-
"""
Custom Quantitative Strategy Template for VECTRA Terminal.
All custom strategies must inherit from BaseStrategy and implement analyze(df, macro_context).
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from backend.core.strategies.base_strategy import BaseStrategy, StrategySignal, ChecklistItem, ChecklistStatus


class CustomQuantitativeStrategy(BaseStrategy):
    """
    Custom Quantitative Strategy Implementation.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.strategy_id = "custom_quant_strategy"
        self.name = "Custom Quant Strategy"
        self.fast_ma_period = self.config.get("fast_period", 10)
        self.slow_ma_period = self.config.get("slow_period", 30)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name,
            "description": "Custom quantitative dual moving average breakout model.",
            "author": "User Quantitative Researcher",
            "version": "1.0",
        }

    def get_default_checklist(self) -> List[ChecklistItem]:
        return [
            ChecklistItem(key="Trend Alignment", value="Pending", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Volume Expansion", value="Pending", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Volatility Filter", value="Pending", status=ChecklistStatus.PENDING),
        ]

    def analyze(self, df: pd.DataFrame, macro_context: Dict[str, Any] = None) -> StrategySignal:
        """
        Bar-by-bar analysis function called by Backtest and Live Execution engines.
        Must return StrategySignal with action, signal ('BUY'/'SELL'/'HOLD'), entry_price, sl, and tp1.
        """
        macro_context = macro_context or {}
        if df is None or len(df) < max(self.slow_ma_period, 50):
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                action="HOLD",
                signal="HOLD",
                entry_price=float(df["close"].iloc[-1]) if len(df) > 0 and "close" in df.columns else 0.0,
                confidence=0.0,
                checklist=self.get_default_checklist(),
            )

        # 1. Indicator calculations (NumPy arrays for maximum speed)
        close_arr = df["close"].to_numpy(dtype=float)
        high_arr = df["high"].to_numpy(dtype=float)
        low_arr = df["low"].to_numpy(dtype=float)
        last_price = float(close_arr[-1])

        fast_ma = np.mean(close_arr[-self.fast_ma_period:])
        slow_ma = np.mean(close_arr[-self.slow_ma_period:])

        # 2. Signal evaluation logic
        action = "HOLD"
        sl = None
        tp1 = None
        confidence = 0.0

        if fast_ma > slow_ma and close_arr[-1] > fast_ma:
            action = "BUY"
            sl = float(np.min(low_arr[-10:]))
            risk = max(0.5, last_price - sl)
            tp1 = float(last_price + risk * 2.0)
            confidence = 0.80

        elif fast_ma < slow_ma and close_arr[-1] < fast_ma:
            action = "SELL"
            sl = float(np.max(high_arr[-10:]))
            risk = max(0.5, sl - last_price)
            tp1 = float(last_price - risk * 2.0)
            confidence = 0.80

        checklist = [
            ChecklistItem(
                key="Trend Alignment",
                value="Bullish Cross" if action == "BUY" else ("Bearish Cross" if action == "SELL" else "Neutral"),
                status=ChecklistStatus.PASSED if action in ("BUY", "SELL") else ChecklistStatus.PENDING,
            ),
            ChecklistItem(
                key="Volume Expansion",
                value="Normal",
                status=ChecklistStatus.PASSED,
            ),
            ChecklistItem(
                key="Volatility Filter",
                value="Active",
                status=ChecklistStatus.PASSED,
            ),
        ]

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            action=action,
            signal=action,
            entry_price=last_price,
            sl=sl,
            tp1=tp1,
            confidence=confidence,
            checklist=checklist,
            metadata={"fast_ma": fast_ma, "slow_ma": slow_ma},
        )
'''
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(template_code)
        return True, f"Created template at backend/core/strategies/{file_path.name}", str(file_path)
    except Exception as e:
        return False, f"Failed to create template: {e}", None


def discover_strategies() -> List[Dict[str, Any]]:
    """
    Scans and returns all available strategies from the centralized 'strategies/' directory,
    plus legacy user documents if any exist.
    """
    strategies: List[Dict[str, Any]] = []
    seen_ids = set()
    strat_dir = get_strategies_dir()

    # 1. Built-in Core Strategies in strategies/
    builtins = [
        {
            "id": "builtin_ict_pro",
            "name": "ICT Zones Pro v4.2 (Asian + FVG)",
            "file_name": "ict_strategy.py",
            "file_path": str(strat_dir / "ict_strategy.py"),
            "class_name": "ICTZonesProStrategy",
            "is_builtin": True,
            "description": "Asian High/Low sweep, Judas swing, Fair Value Gap and Killzone filter."
        },
        {
            "id": "builtin_wyckoff",
            "name": "Wyckoff Momentum Pro (Vectorized)",
            "file_name": "wyckoff_vectorized.py",
            "file_path": str(strat_dir / "wyckoff_vectorized.py"),
            "class_name": "WyckoffMomentumStrategy",
            "is_builtin": True,
            "description": "Vectorized NumPy ATR envelope and Volume expansion momentum model."
        },
        {
            "id": "builtin_ema_stress",
            "name": "EMA Dual Cross (Resilience Benchmark)",
            "file_name": "ema_stress_test.py",
            "file_path": str(strat_dir / "ema_stress_test.py"),
            "class_name": "EMAStressTestStrategy",
            "is_builtin": True,
            "description": "Fast EMA10 / Slow EMA50 crossover with dynamic risk sizing."
        },
    ]

    for b in builtins:
        if Path(b["file_path"]).exists():
            strategies.append(b)
            seen_ids.add(b["id"])
            seen_ids.add(b["file_name"])

    # 2. Scan all other .py files in strategies/ (including custom_ict_fvg.py and user files)
    ignore_files = {"__init__.py", "strategy_loader.py", "base_strategy.py"}
    for py_file in sorted(strat_dir.glob("*.py")):
        if py_file.name in ignore_files or py_file.name in seen_ids:
            continue
        valid, _, class_name = validate_strategy_file(str(py_file))
        if valid and class_name:
            strategies.append({
                "id": f"strat_{py_file.stem}",
                "name": f"{class_name} (Custom)",
                "file_name": py_file.name,
                "file_path": str(py_file),
                "class_name": class_name,
                "is_builtin": False,
                "description": f"Strategy loaded from strategies/{py_file.name}"
            })
            seen_ids.add(f"strat_{py_file.stem}")
            seen_ids.add(py_file.name)

    # 3. Check legacy Documents folder for backward compatibility
    legacy_docs = Path(os.path.expanduser("~")) / "Documents" / "Quant_AI" / "Strategies"
    if legacy_docs.exists():
        for py_file in sorted(legacy_docs.glob("*.py")):
            if py_file.name in seen_ids:
                continue
            valid, _, class_name = validate_strategy_file(str(py_file))
            if valid and class_name:
                strategies.append({
                    "id": f"doc_{py_file.stem}",
                    "name": f"{class_name} (Docs)",
                    "file_name": py_file.name,
                    "file_path": str(py_file),
                    "class_name": class_name,
                    "is_builtin": False,
                    "description": f"Loaded from Documents/Quant_AI/Strategies/{py_file.name}"
                })
                seen_ids.add(f"doc_{py_file.stem}")

    return strategies


def load_strategy_instance(file_path: str, class_name: str, config: Optional[Dict] = None) -> Optional[Any]:
    """
    Dynamically loads and instantiates a strategy class at runtime,
    enforcing AST Security Sandbox verification on untrusted code.
    """
    p = Path(file_path)
    if not p.exists():
        logger.error(f"Strategy file not found: {file_path}")
        return None

    # AST Sandbox verification before executing code
    is_builtin = p.name in ("ict_strategy.py", "wyckoff_vectorized.py", "ema_stress_test.py")
    valid, msg, _ = validate_strategy_file(str(p), is_builtin=is_builtin)
    if not valid:
        logger.error(f"[StrategyLoader] Refused to load untrusted strategy '{p.name}': {msg}")
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


def get_strategy_instance(identifier: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Any:
    """
    Polymorphic factory resolving any strategy by ID, name, or system config.
    Returns a typed BaseStrategy instance. Guarantees non-null return via ICTZonesProStrategy fallback.
    """
    from backend.core.strategies.ict_strategy import ICTZonesProStrategy
    from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
    from backend.core.strategies.ema_stress_test import EMAStressTestStrategy

    cfg_id = identifier
    if not cfg_id:
        try:
            import json
            from pathlib import Path
            proj_root = Path(__file__).resolve().parent.parent.parent.parent
            cfg_p = proj_root / "config" / "settings.json"
            if cfg_p.exists():
                with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                    cfg_data = json.load(f_cfg)
                    cfg_id = cfg_data.get("strategy", "builtin_ict_pro")
        except Exception:
            cfg_id = "builtin_ict_pro"

    id_str = str(cfg_id or "builtin_ict_pro").strip()
    id_lower = id_str.lower()

    # 1. Check known built-ins first for optimal zero-overhead speed
    if "wyckoff" in id_lower:
        return WyckoffMomentumStrategy(config)
    if "ema" in id_lower:
        return EMAStressTestStrategy(config)
    if "ict" in id_lower:
        return ICTZonesProStrategy(config)

    # 2. Check dynamic discovery
    for s in discover_strategies():
        s_id = s.get("id", "").lower()
        s_name = s.get("name", "").lower()
        s_class = s.get("class_name", "").lower()
        if (
            id_lower == s_id
            or id_lower == s_name
            or id_lower == s_name.split("(")[0].strip()
            or id_lower == s_class
        ):
            inst = load_strategy_instance(s["file_path"], s["class_name"], config)
            if inst is not None:
                return inst

    # Fallback to ICT default
    return ICTZonesProStrategy(config)

