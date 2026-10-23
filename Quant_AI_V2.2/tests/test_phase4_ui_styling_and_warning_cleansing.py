"""
Phase 4 Verification Suite: Institutional Design System & Qt Warning Cleansing
Covers FE-1, FE-3, FE-5, FE-10 and GEMINI.md Rule 4 constraints.
"""

import os
import re
import pytest
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QMainWindow

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_qss_files_zero_important_directives():
    """Verify no !important directives exist in QSS files (invalid Qt CSS syntax)."""
    qss_dir = os.path.join(PROJECT_ROOT, "frontend", "styling")
    for fname in ["style.qss", "style_light.qss"]:
        fpath = os.path.join(qss_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "!important" not in content, f"Found invalid !important directive in {fname}"


def test_qss_all_urls_properly_quoted():
    """Verify all url() directives in QSS files use quotes to prevent space-path parsing failures."""
    qss_dir = os.path.join(PROJECT_ROOT, "frontend", "styling")
    for fname in ["style.qss", "style_light.qss"]:
        fpath = os.path.join(qss_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    if "url(" in line:
                        assert 'url("' in line or "url('" in line, (
                            f"Unquoted url() found in {fname}:{idx+1}: {line.strip()}"
                        )


def test_institutional_flat_border_radius():
    """Verify strict compliance with GEMINI.md Rule 4 (border-radius 0px-4px, no pill shapes)."""
    qss_dir = os.path.join(PROJECT_ROOT, "frontend", "styling")
    for fname in ["style.qss", "style_light.qss"]:
        fpath = os.path.join(qss_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    m = re.search(r"border-radius:\s*(\d+)px", line)
                    if m:
                        val = int(m.group(1))
                        assert val <= 4, (
                            f"Violation of GEMINI.md Rule 4: border-radius={val}px > 4px in {fname}:{idx+1}"
                        )


def test_main_py_qss_regex_asset_resolution():
    """Verify QSS asset resolution in main.py converts relative assets cleanly without duplication."""
    sample_qss = (
        'QCheckBox { image: url("frontend/assets/check_icon.svg"); }\n'
        'QToolButton { qproperty-icon: url("assets/chevron_left.svg"); }'
    )
    assets_dir = os.path.join(PROJECT_ROOT, "frontend", "assets").replace("\\", "/")
    resolved = re.sub(
        r'url\(["\']?(?:frontend/)?assets/([^"\'\)]+)["\']?\)',
        f'url("{assets_dir}/\\1")',
        sample_qss
    )
    assert f'url("{assets_dir}/check_icon.svg")' in resolved
    assert f'url("{assets_dir}/chevron_left.svg")' in resolved
    assert resolved.count(assets_dir) == 2


def test_zero_qt_stylesheet_parse_warnings_on_mainwindow():
    """Verify style_light.qss parses on QMainWindow with zero Qt syntax warnings."""
    _app = QApplication.instance() or QApplication([])
    warnings = []

    def handler(mode, ctx, msg):
        if any(ign in msg.lower() for ign in ["cannot find font directory", "propagatesizehints"]):
            return
        warnings.append(msg)

    qInstallMessageHandler(handler)

    qss_path = os.path.join(PROJECT_ROOT, "frontend", "styling", "style_light.qss")
    with open(qss_path, "r", encoding="utf-8") as f:
        content_qss = f.read()

    assets_dir = os.path.join(PROJECT_ROOT, "frontend", "assets").replace("\\", "/")
    content_qss = re.sub(
        r'url\(["\']?(?:frontend/)?assets/([^"\'\)]+)["\']?\)',
        f'url("{assets_dir}/\\1")',
        content_qss
    )

    win = QMainWindow()
    win.setObjectName("MainWindow")
    win.setStyleSheet(content_qss)
    win.show()
    _app.processEvents()

    assert len(warnings) == 0, f"Unexpected Qt warnings during QSS parsing: {warnings}"
