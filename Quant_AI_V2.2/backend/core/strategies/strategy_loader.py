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
            "class_name": "VectorizedBacktester",
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
    ignore_files = {"__init__.py", "strategy_loader.py"}
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
