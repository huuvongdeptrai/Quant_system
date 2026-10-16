# -*- coding: utf-8 -*-
"""
Interactive Drawing Engine for Quant Terminal Chart.
Provides TradingView-grade interactive chart annotations:
1. Crosshair Mode (Cursor coordinates and hover inspection)
2. Trendline Tool (Click & drag to draw permanent support/resistance trendlines with anchor dots)
3. Rectangle / Zone Tool (Click & drag to draw supply/demand zones / order blocks / FVG)
4. Ruler Tool (Click & drag to measure delta price, percentage change, pips, and bar duration)
5. Clear All Drawings (Trash / clear action)
"""

import math
from PySide6.QtCore import Qt, QObject, QEvent, QPointF
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import QGraphicsRectItem
import pyqtgraph as pg
from backend.infrastructure.brokers.mt5_safe import mt5


class ChartDrawingEngine(QObject):
    """Event filter and drawing manager attached to plot_widget."""

    MODE_CROSSHAIR = "crosshair"
    MODE_TRENDLINE = "trendline"
    MODE_RECTANGLE = "rectangle"
    MODE_RULER = "ruler"

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.plot_widget = window.plot_widget
        self.mode = self.MODE_CROSSHAIR

        # Collections
        self.user_drawings = []  # List of {type, items: [...], data: {...}}
        self.fvg_items = []      # Auto-detected FVG items
        self.ruler_items = []    # Active ruler measurement visual items

        # In-progress drag state
        self.drag_start = None   # (x, y) view coordinates
        self.temp_items = []     # temporary preview items while dragging

        # Toolbar button references
        self.btn_crosshair = None
        self.btn_trendline = None
        self.btn_rect = None
        self.btn_ruler = None
        self.btn_gear = None
        self.btn_clear = None

        # Install event filter on viewport to intercept mouse events before ViewBox
        self.plot_widget.viewport().installEventFilter(self)

    def set_toolbar_buttons(self, btn_cross, btn_trend, btn_rect, btn_ruler, btn_gear, btn_clear=None):
        self.btn_crosshair = btn_cross
        self.btn_trendline = btn_trend
        self.btn_rect = btn_rect
        self.btn_ruler = btn_ruler
        self.btn_gear = btn_gear
        self.btn_clear = btn_clear
        self._update_button_styles()

    def set_mode(self, new_mode: str):
        if self.mode == new_mode and new_mode != self.MODE_CROSSHAIR:
            # Clicking an already active drawing tool toggles back to crosshair
            new_mode = self.MODE_CROSSHAIR

        self._cancel_active_drag()
        self.mode = new_mode

        if new_mode == self.MODE_CROSSHAIR:
            self.plot_widget.viewport().setCursor(Qt.ArrowCursor)
            self.window._crosshair_enabled = True
            if hasattr(self.window, "vLine"): self.window.vLine.setVisible(True)
            if hasattr(self.window, "hLine"): self.window.hLine.setVisible(True)
            if hasattr(self.window, "crosshair_label"): self.window.crosshair_label.setVisible(True)
        else:
            self.plot_widget.viewport().setCursor(Qt.CrossCursor)
            # In drawing or ruler mode, freeze or dim crosshair lines to avoid visual clutter
            if hasattr(self.window, "vLine"): self.window.vLine.setVisible(False)
            if hasattr(self.window, "hLine"): self.window.hLine.setVisible(False)
            if hasattr(self.window, "crosshair_label"): self.window.crosshair_label.setVisible(False)

        self._update_button_styles()

    def _update_button_styles(self):
        is_d = getattr(self.window, "is_dark_theme", False)
        style_fn = getattr(self.window, "_get_tool_btn_style", None)
        if not style_fn:
            return

        if self.btn_crosshair:
            self.btn_crosshair.setStyleSheet(style_fn(is_d, is_active=(self.mode == self.MODE_CROSSHAIR)))
            self.btn_crosshair.setChecked(self.mode == self.MODE_CROSSHAIR)
        if self.btn_trendline:
            self.btn_trendline.setStyleSheet(style_fn(is_d, is_active=(self.mode == self.MODE_TRENDLINE)))
            self.btn_trendline.setChecked(self.mode == self.MODE_TRENDLINE)
        if self.btn_rect:
            self.btn_rect.setStyleSheet(style_fn(is_d, is_active=(self.mode == self.MODE_RECTANGLE)))
            self.btn_rect.setChecked(self.mode == self.MODE_RECTANGLE)
        if self.btn_ruler:
            self.btn_ruler.setStyleSheet(style_fn(is_d, is_active=(self.mode == self.MODE_RULER), is_accent=True))
            self.btn_ruler.setChecked(self.mode == self.MODE_RULER)

    def _cancel_active_drag(self):
        for item in self.temp_items:
            try:
                self.plot_widget.removeItem(item)
            except Exception:
                pass
        self.temp_items.clear()
        self.drag_start = None

    def clear_ruler(self):
        for item in self.ruler_items:
            try:
                self.plot_widget.removeItem(item)
            except Exception:
                pass
        self.ruler_items.clear()

    def clear_user_drawings(self):
        for d in self.user_drawings:
            for it in d.get("items", []):
                try:
                    self.plot_widget.removeItem(it)
                except Exception:
                    pass
        self.user_drawings.clear()
        self.clear_ruler()

    def toggle_fvg(self, checked: bool):
        self.window._fvg_visible = checked
        for it in self.fvg_items:
            if it:
                it.setVisible(checked)

    def toggle_poc(self, checked: bool):
        self.window._poc_visible = checked
        if hasattr(self.window, "line_tpoc") and self.window.line_tpoc:
            self.window.line_tpoc.setVisible(checked)
        if hasattr(self.window, "line_vpoc") and self.window.line_vpoc:
            self.window.line_vpoc.setVisible(checked)

    def re_add_to_plot(self):
        """Called after plot_widget.clear() to restore user drawings, ruler, and FVG items."""
        curr_items = set(self.plot_widget.items())

        # Re-add user drawn annotations
        for d in self.user_drawings:
            for it in d.get("items", []):
                if it not in curr_items:
                    try:
                        self.plot_widget.addItem(it, ignoreBounds=True)
                    except Exception:
                        pass

        # Re-add ruler items if present
        for it in self.ruler_items:
            if it not in curr_items:
                try:
                    self.plot_widget.addItem(it, ignoreBounds=True)
                except Exception:
                    pass

        # Re-apply FVG visibility
        fvg_vis = getattr(self.window, "_fvg_visible", True)
        for it in self.fvg_items:
            if it not in curr_items:
                try:
                    self.plot_widget.addItem(it, ignoreBounds=True)
                except Exception:
                    pass
            it.setVisible(fvg_vis)

        # Re-apply POC visibility
        poc_vis = getattr(self.window, "_poc_visible", True)
        if hasattr(self.window, "line_tpoc") and self.window.line_tpoc:
            if self.window.line_tpoc not in curr_items:
                try: self.plot_widget.addItem(self.window.line_tpoc, ignoreBounds=True)
                except Exception: pass
            self.window.line_tpoc.setVisible(poc_vis)
        if hasattr(self.window, "line_vpoc") and self.window.line_vpoc:
            if self.window.line_vpoc not in curr_items:
                try: self.plot_widget.addItem(self.window.line_vpoc, ignoreBounds=True)
                except Exception: pass
            self.window.line_vpoc.setVisible(poc_vis)

    def eventFilter(self, obj, event):
        """Intercept mouse events on plot_widget viewport for interactive drawing tools."""
        if obj != self.plot_widget.viewport():
            return False

        ev_type = event.type()

        # Handle Escape / Delete keys
        if ev_type == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._cancel_active_drag()
                self.clear_ruler()
                self.set_mode(self.MODE_CROSSHAIR)
                return True
            elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                if self.user_drawings:
                    last_d = self.user_drawings.pop()
                    for it in last_d.get("items", []):
                        try: self.plot_widget.removeItem(it)
                        except Exception: pass
                self.clear_ruler()
                return True

        # In Crosshair mode: pass all mouse events to ViewBox for normal panning/zooming
        if self.mode == self.MODE_CROSSHAIR:
            return False

        # In Drawing or Ruler mode: intercept left clicks and drags
        if ev_type == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                scene_pos = self.plot_widget.mapToScene(pos)
                if self.plot_widget.plotItem.vb.sceneBoundingRect().contains(scene_pos):
                    view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
                    self.drag_start = (view_pos.x(), view_pos.y())
                    self.clear_ruler()
                    return True
            elif event.button() == Qt.MouseButton.RightButton:
                self._cancel_active_drag()
                self.clear_ruler()
                self.set_mode(self.MODE_CROSSHAIR)
                return True

        elif ev_type == QEvent.Type.MouseMove:
            if self.drag_start is not None:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                scene_pos = self.plot_widget.mapToScene(pos)
                view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
                x1, y1 = self.drag_start
                x2, y2 = view_pos.x(), view_pos.y()
                self._update_live_preview(x1, y1, x2, y2)
                return True

        elif ev_type == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton and self.drag_start is not None:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                scene_pos = self.plot_widget.mapToScene(pos)
                view_pos = self.plot_widget.plotItem.vb.mapSceneToView(scene_pos)
                x1, y1 = self.drag_start
                x2, y2 = view_pos.x(), view_pos.y()

                self._commit_drawing(x1, y1, x2, y2)
                self._cancel_active_drag()

                # After drawing a trendline or rectangle, return to crosshair mode
                if self.mode in (self.MODE_TRENDLINE, self.MODE_RECTANGLE):
                    self.set_mode(self.MODE_CROSSHAIR)
                return True

        return False

    def _update_live_preview(self, x1, y1, x2, y2):
        is_d = getattr(self.window, "is_dark_theme", False)

        if self.mode == self.MODE_TRENDLINE:
            if not self.temp_items:
                line_item = pg.PlotCurveItem(
                    pen=pg.mkPen(color="#2563eb", width=1.8, style=Qt.DashLine)
                )
                self.plot_widget.addItem(line_item, ignoreBounds=True)
                self.temp_items.append(line_item)
            else:
                line_item = self.temp_items[0]
            line_item.setData([x1, x2], [y1, y2])

        elif self.mode == self.MODE_RECTANGLE:
            top_y = max(y1, y2)
            bot_y = min(y1, y2)
            left_x = min(x1, x2)
            right_x = max(x1, x2)
            w = max(0.5, right_x - left_x)
            h = max(0.00001, top_y - bot_y)

            if not self.temp_items:
                rect_item = QGraphicsRectItem(left_x, bot_y, w, h)
                rect_item.setBrush(pg.mkBrush(245, 158, 11, 40))
                rect_item.setPen(pg.mkPen(color=pg.mkColor(245, 158, 11, 160), width=1.2, style=Qt.DashLine))
                self.plot_widget.addItem(rect_item, ignoreBounds=True)
                self.temp_items.append(rect_item)
            else:
                rect_item = self.temp_items[0]
                rect_item.setRect(left_x, bot_y, w, h)

        elif self.mode == self.MODE_RULER:
            self._render_ruler_visuals(x1, y1, x2, y2, is_preview=True)

    def _render_ruler_visuals(self, x1, y1, x2, y2, is_preview=False):
        top_y = max(y1, y2)
        bot_y = min(y1, y2)
        left_x = min(x1, x2)
        right_x = max(x1, x2)
        w = max(0.2, right_x - left_x)
        h = max(0.00001, top_y - bot_y)

        delta_p = y2 - y1
        delta_pct = (delta_p / y1 * 100.0) if y1 != 0 else 0.0
        delta_bars = int(round(abs(x2 - x1)))

        clean_sym = getattr(self.window, "current_sym", "XAUUSD").split("\n")[0].strip()
        s_info = mt5.symbol_info(clean_sym)
        pt = s_info.point if s_info else (0.01 if y1 > 100 else 0.0001)
        pips = (delta_p / (pt * 10.0)) if pt > 0 else delta_p

        digits = s_info.digits if s_info else (2 if y1 > 100 else 5)
        sign = "+" if delta_p >= 0 else ""
        ruler_txt = f"{sign}{delta_p:.{digits}f} ({sign}{delta_pct:.2f}%)  |  {sign}{pips:.1f} pips  |  {delta_bars} bars"

        is_bull = delta_p >= 0
        fill_color = pg.mkBrush(16, 185, 129, 45) if is_bull else pg.mkBrush(239, 68, 68, 45)
        pen_color = pg.mkPen(color=pg.mkColor(16, 185, 129, 180), width=1, style=Qt.DashLine) if is_bull else pg.mkPen(color=pg.mkColor(239, 68, 68, 180), width=1, style=Qt.DashLine)
        pill_bg = pg.mkBrush(6, 78, 59, 230) if is_bull else pg.mkBrush(127, 29, 29, 230)

        target_list = self.temp_items if is_preview else self.ruler_items

        if not target_list:
            r_box = QGraphicsRectItem(left_x, bot_y, w, h)
            r_box.setBrush(fill_color)
            r_box.setPen(pen_color)
            self.plot_widget.addItem(r_box, ignoreBounds=True)

            r_line = pg.PlotCurveItem(pen=pg.mkPen(color="#2563eb", width=1.5, style=Qt.DashLine))
            r_line.setData([x1, x2], [y1, y2])
            self.plot_widget.addItem(r_line, ignoreBounds=True)

            r_lbl = pg.TextItem(text=ruler_txt, color="#ffffff", fill=pill_bg, anchor=(0, 1))
            r_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
            r_lbl.setPos(x2, y2)
            self.plot_widget.addItem(r_lbl, ignoreBounds=True)

            target_list.extend([r_box, r_line, r_lbl])
        else:
            r_box, r_line, r_lbl = target_list[0], target_list[1], target_list[2]
            r_box.setRect(left_x, bot_y, w, h)
            r_box.setBrush(fill_color)
            r_box.setPen(pen_color)
            r_line.setData([x1, x2], [y1, y2])
            r_lbl.setText(ruler_txt)
            r_lbl.setColor("#ffffff")
            r_lbl.fill = pill_bg
            r_lbl.setPos(x2, y2)

    def _commit_drawing(self, x1, y1, x2, y2):
        dist_x = abs(x2 - x1)
        dist_y = abs(y2 - y1)

        # Minimum drag distance to prevent accidental micro-clicks
        if dist_x < 0.5 and dist_y < 0.00005:
            return

        if self.mode == self.MODE_TRENDLINE:
            # Permanent crisp Trendline with subtle endpoint dots
            line_item = pg.PlotCurveItem(
                pen=pg.mkPen(color="#2563eb", width=2.0, style=Qt.SolidLine)
            )
            line_item.setData([x1, x2], [y1, y2])
            self.plot_widget.addItem(line_item, ignoreBounds=True)

            start_dot = pg.PlotCurveItem(
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=pg.mkBrush("#2563eb"),
                symbolPen=pg.mkPen("#ffffff", width=1)
            )
            start_dot.setData([x1], [y1])
            self.plot_widget.addItem(start_dot, ignoreBounds=True)

            end_dot = pg.PlotCurveItem(
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=pg.mkBrush("#2563eb"),
                symbolPen=pg.mkPen("#ffffff", width=1)
            )
            end_dot.setData([x2], [y2])
            self.plot_widget.addItem(end_dot, ignoreBounds=True)

            drawing_record = {
                "type": "trendline",
                "items": [line_item, start_dot, end_dot],
                "coords": (x1, y1, x2, y2)
            }
            self.user_drawings.append(drawing_record)

        elif self.mode == self.MODE_RECTANGLE:
            top_y = max(y1, y2)
            bot_y = min(y1, y2)
            left_x = min(x1, x2)
            right_x = max(x1, x2)
            w = right_x - left_x
            h = top_y - bot_y

            rect_item = QGraphicsRectItem(left_x, bot_y, w, h)
            rect_item.setBrush(pg.mkBrush(245, 158, 11, 45))
            rect_item.setPen(pg.mkPen(color=pg.mkColor(245, 158, 11, 180), width=1.2, style=Qt.SolidLine))
            self.plot_widget.addItem(rect_item, ignoreBounds=True)

            lbl_zone = pg.TextItem(text="ZONE", color=(245, 158, 11, 220), anchor=(0, 1))
            lbl_zone.setFont(QFont("Consolas", 8, QFont.Bold))
            lbl_zone.setPos(left_x + 0.5, top_y)
            self.plot_widget.addItem(lbl_zone, ignoreBounds=True)

            drawing_record = {
                "type": "rectangle",
                "items": [rect_item, lbl_zone],
                "coords": (left_x, bot_y, w, h)
            }
            self.user_drawings.append(drawing_record)

        elif self.mode == self.MODE_RULER:
            # Commit the ruler measurement onto ruler_items so it stays visible
            self.clear_ruler()
            self._render_ruler_visuals(x1, y1, x2, y2, is_preview=False)
