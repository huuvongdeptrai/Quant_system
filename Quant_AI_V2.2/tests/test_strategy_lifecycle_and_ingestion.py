# -*- coding: utf-8 -*-
"""
Unit tests for Quantitative Strategy Ingestion, Lifecycle Management, and Security Sandbox Guard.
"""

import os
import pytest
from pathlib import Path

from backend.core.strategies.strategy_loader import (
    discover_strategies,
    import_strategy_file,
    delete_strategy_file,
    create_template_strategy,
    validate_strategy_file,
    get_strategies_dir,
    get_strategy_instance
)
from backend.core.strategies.base_strategy import BaseStrategy


class TestStrategyLifecycleAndIngestion:

    def test_strategy_discovery_includes_core(self):
        strats = discover_strategies()
        assert len(strats) >= 3
        ids = [s["id"] for s in strats]
        assert "builtin_ict_pro" in ids
        assert "builtin_wyckoff" in ids
        assert "builtin_ema_stress" in ids

    def test_core_strategy_deletion_is_strictly_blocked(self):
        ok, msg = delete_strategy_file("ict_strategy.py")
        assert ok is False
        assert "Cannot delete protected core strategy" in msg

        ok2, msg2 = delete_strategy_file("wyckoff_vectorized.py")
        assert ok2 is False
        assert "Cannot delete protected core strategy" in msg2

    def test_create_and_archive_custom_template_strategy(self, tmp_path):
        # 1. Create a template
        test_strat_name = "test_pytest_dummy_strat.py"
        ok, msg, created_path = create_template_strategy(test_strat_name)
        assert ok is True
        assert Path(created_path).exists()

        try:
            # 2. Check discovery sees it
            strats_after = discover_strategies()
            found = any(s["file_name"] == test_strat_name for s in strats_after)
            assert found is True

            # 3. Check dynamic instantiation
            inst = get_strategy_instance("test_pytest_dummy_strat")
            assert inst is not None
            assert isinstance(inst, BaseStrategy)

            # 4. Safely delete/archive it
            del_ok, del_msg = delete_strategy_file(test_strat_name)
            assert del_ok is True
            assert "archived" in del_msg

            # 5. Verify it is moved to archive and no longer discovered
            strat_dir = get_strategies_dir()
            assert not (strat_dir / test_strat_name).exists()
            assert (strat_dir / "archive" / test_strat_name).exists()

            strats_final = discover_strategies()
            assert not any(s["file_name"] == test_strat_name for s in strats_final)

        finally:
            # Clean up archive if exists
            archived_p = get_strategies_dir() / "archive" / test_strat_name
            if archived_p.exists():
                archived_p.unlink()

    def test_ast_sandbox_guard_blocks_unauthorized_imports(self, tmp_path):
        # Create a malicious script attempting os.system
        malicious_file = tmp_path / "bad_actor_strat.py"
        malicious_file.write_text("""
import os
from backend.core.strategies.base_strategy import BaseStrategy

class BadActorStrategy(BaseStrategy):
    def analyze(self, df, macro_context=None):
        os.system("echo hacked")
        return None
""", encoding="utf-8")

        valid, msg, cls_name = validate_strategy_file(str(malicious_file), is_builtin=False)
        assert valid is False
        assert "Bảo mật từ chối" in msg or "AST Sandbox Guard" in msg
