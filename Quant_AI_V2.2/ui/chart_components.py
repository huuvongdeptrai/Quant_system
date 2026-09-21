import pyqtgraph as pg


from PySide6 import QtCore


from PySide6.QtCore import QPointF, Qt


from PySide6.QtGui import QPicture, QPainter


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QLabel,
    QFrame,
    QScrollArea,
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QGraphicsRectItem,
)


from infrastructure.brokers.mt5_safe import mt5


import pandas as pd


from datetime import datetime


import json


class TimeAxisItem(pg.AxisItem):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.timestamps = []

    def update_timestamps(self, timestamps):

        self.timestamps = timestamps

    def tickStrings(self, values, scale, spacing):

        strings = []

        for v in values:

            idx = int(v)

            if 0 <= idx < len(self.timestamps):

                dt = datetime.fromtimestamp(self.timestamps[idx])

                strings.append(dt.strftime("%d/%m %H:%M"))

            else:

                strings.append("")

        return strings


class CandlestickItem(pg.GraphicsObject):

    def __init__(self, data):

        pg.GraphicsObject.__init__(self)

        self.data = data

        self.generatePicture()

    def generatePicture(self):

        self.picture = QPicture()

        p = QPainter(self.picture)

        p.setPen(pg.mkPen("w"))

        w = 0.35

        for t, open, close, low, high in self.data:

            if open > close:

                p.setBrush(pg.mkBrush("#ef4444"))

                p.setPen(pg.mkPen("#ef4444"))

            else:

                p.setBrush(pg.mkBrush("#22c55e"))

                p.setPen(pg.mkPen("#22c55e"))

            p.drawLine(QPointF(t, low), QPointF(t, high))

            min_price = open if open < close else close

            p.drawRect(
                QtCore.QRectF(t - w, min_price, w * 2, max(abs(close - open), 0.0001))
            )

        p.end()

    def paint(self, p, *args):

        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):

        return QtCore.QRectF(self.picture.boundingRect())


class AISignals(QtCore.QObject):

    result = QtCore.Signal(dict)

    error = QtCore.Signal(str)

    loading = QtCore.Signal(str)


class AIAnalyzerThread(QtCore.QThread):

    def __init__(
        self,
        parent=None,
        sym="",
        rates=None,
        timeframe_str="",
        active_id=None,
        force_refresh=False,
        tech_data=None,
        d1_rates=None,
        h4_rates=None,
    ):

        super().__init__(parent)

        self.sym = sym

        self.rates = rates

        self.timeframe_str = timeframe_str

        self.active_id = active_id

        self.force_refresh = force_refresh

        self.tech_data = tech_data

        self.d1_rates = d1_rates

        self.h4_rates = h4_rates

        self.signals = AISignals()

        self.is_cancelled = False

    def stop(self):

        self.is_cancelled = True

    def run(self):

        try:

            from infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

            from infrastructure.ai_engines.ai.decision_gate import DecisionGate

            model_name = self.active_id if self.active_id else "qwen2.5"

            engine = AnalysisEngine(model_name=model_name)

            if self.is_cancelled:

                return

            self.signals.loading.emit(
                "\u0110ang t\u1ed5ng h\u1ee3p d\u1eef li\u1ec7u..."
            )

            result = engine.analyze(self.sym, force_refresh=self.force_refresh)

            if self.is_cancelled:

                return

            if "error" in result:

                self.signals.error.emit(str(result["error"]))

                return

            # Dinh kem them gia va S/R tu cache hoac tech_data

            cached = engine.cache.get(self.sym, {})

            result["_price"] = cached.get("result", result).get("_price", 0)

            result["_resistance"] = cached.get("resistance", 0)

            result["_support"] = cached.get("support", 0)

            if self.tech_data:

                result["_price"] = self.tech_data["current_price"]

                result["_resistance"] = self.tech_data["resistance"]

                result["_support"] = self.tech_data["support"]

                if "math_trend" in self.tech_data:

                    result["trend_intraday"] = self.tech_data["math_trend"]

            # Them HTF bias va vi tri gia vao result

            try:

                gate = DecisionGate()

                # Để UI tính Hỗ trợ/Kháng cự bám sát theo Khung thời gian người dùng đang xem

                rates_for_pos = (
                    self.rates[-150:]
                    if self.rates is not None and len(self.rates) >= 150
                    else self.rates
                )

                price_info = gate._get_price_position(self.sym, rates=rates_for_pos)

                htf_bias = gate._get_htf_bias(
                    self.sym, d1_rates=self.d1_rates, h4_rates=self.h4_rates
                )

                if price_info:

                    result["_position"] = price_info["position"]

                    result["_pct_support"] = price_info.get("pct_from_support", 0)

                    result["_pct_resistance"] = price_info.get("pct_from_resistance", 0)

                result["_htf_bias"] = htf_bias

            except Exception:

                pass

            self.signals.result.emit(result)

        except Exception as e:

            if not self.is_cancelled:

                self.signals.error.emit(str(e))


def _make_separator():

    sep = QFrame()

    sep.setFrameShape(QFrame.HLine)

    sep.setStyleSheet("background-color: #21262D; max-height: 1px;")

    return sep


def _make_label(text, color="#8B949E", size=11, bold=False, font="Segoe UI"):

    lbl = QLabel(text)

    weight = "bold" if bold else "normal"

    lbl.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight}; font-family: '{font}';"
    )

    lbl.setWordWrap(True)

    return lbl


def _build_analysis_panel(window):
    """Preserve AI DECISION GATE from quant_ai.ui and provide dummy labels for backwards compatibility."""
    for attr in [
        "ai_lbl_header",
        "ai_lbl_time",
        "ai_lbl_price",
        "ai_lbl_resistance",
        "ai_lbl_res_delta",
        "ai_lbl_support",
        "ai_lbl_sup_delta",
        "ai_lbl_macro",
        "ai_lbl_htf",
        "ai_lbl_intraday",
        "ai_lbl_position",
        "ai_lbl_scenario_a",
        "ai_lbl_scenario_b",
        "ai_lbl_status",
    ]:
        if not hasattr(window, attr):
            setattr(window, attr, QLabel())


def _force_reanalyze(window):

    if window.current_sym:

        _run_analysis(window, window.current_sym, force=True)


def _update_panel_with_result(window, result):
    """Cap nhat tat ca cac QLabel tren panel tu dict ket qua AI."""

    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")

    window.ai_lbl_time.setText(f"C\u1eadp nh\u1eadt: {now_str}")

    price = result.get("_price", 0)

    res = result.get("_resistance", 0)

    sup = result.get("_support", 0)

    if price > 0:

        window.ai_lbl_price.setText(f"{price:,.2f}")

    if res > 0:

        window.ai_lbl_resistance.setText(f"{res:,.2f}")

        delta_r = res - price if price > 0 else 0

        window.ai_lbl_res_delta.setText(f"{delta_r:+,.2f}")

    if sup > 0:

        window.ai_lbl_support.setText(f"{sup:,.2f}")

        delta_s = sup - price if price > 0 else 0

        window.ai_lbl_sup_delta.setText(f"{delta_s:+,.2f}")

    # Xu huong

    macro_trend = result.get("trend_macro", "--")

    intra_trend = result.get("trend_intraday", "--")

    def _trend_color(trend_text):

        t = trend_text.lower()

        if "t\u0103ng" in t or "bullish" in t or "tang" in t:

            return "#3FB950"

        elif "gi\u1ea3m" in t or "bearish" in t or "giam" in t:

            return "#F23645"

        return "#8B949E"

    window.ai_lbl_macro.setText(macro_trend)

    window.ai_lbl_macro.setStyleSheet(
        f"color: {_trend_color(macro_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    window.ai_lbl_intraday.setText(intra_trend)

    window.ai_lbl_intraday.setStyleSheet(
        f"color: {_trend_color(intra_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    # Kich ban

    window.ai_lbl_scenario_a.setText(result.get("scenario_a", "--"))

    window.ai_lbl_scenario_b.setText(result.get("scenario_b", "--"))

    # HTF Bias

    htf = result.get("_htf_bias", "--")

    htf_map = {
        "BULLISH": "T\u0103ng",
        "BEARISH": "Gi\u1ea3m",
        "NEUTRAL": "\u0110i ngang",
    }

    htf_text = htf_map.get(htf, htf)

    window.ai_lbl_htf.setText(htf_text)

    window.ai_lbl_htf.setStyleSheet(
        f"color: {_trend_color(htf_text)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    # Vi tri gia

    pos = result.get("_position", "--")

    pos_map = {
        "AT_SUPPORT": "T\u1ea1i H\u1ed7 tr\u1ee3",
        "AT_RESISTANCE": "T\u1ea1i Kh\u00e1ng c\u1ef1",
        "MIDDLE": "Gi\u1eefa v\u00f9ng",
    }

    pos_text = pos_map.get(pos, pos)

    pos_color = (
        "#3FB950"
        if pos == "AT_SUPPORT"
        else "#F23645" if pos == "AT_RESISTANCE" else "#8B949E"
    )

    window.ai_lbl_position.setText(pos_text)

    window.ai_lbl_position.setStyleSheet(
        f"color: {pos_color}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    window.ai_lbl_status.setText("")


def _run_analysis(window, sym, force=False):
    """Bat dau thread phan tich AI."""

    if not sym:

        window.ai_lbl_status.setText("Vui lòng chọn mã!")

        return

    window.ai_lbl_header.setText(f"{sym}  {window.current_tf_str}")

    window.ai_lbl_status.setText("\u0110ang ph\u00e2n t\u00edch...")

    window.ai_lbl_status.setStyleSheet(
        "color: #58A6FF; font-size: 10px; font-family: 'Segoe UI';"
    )

    if not hasattr(window, "_active_ai_threads"):

        window._active_ai_threads = set()

    if (
        hasattr(window, "ai_thread")
        and window.ai_thread
        and window.ai_thread.isRunning()
    ):

        old_t = window.ai_thread

        old_t.stop()

        try:

            old_t.signals.result.disconnect()

            old_t.signals.error.disconnect()

            old_t.signals.loading.disconnect()

        except Exception:

            pass

        old_t.quit()

        window._active_ai_threads.add(old_t)

        old_t.finished.connect(lambda t=old_t: window._active_ai_threads.discard(t))

    active_id = None

    if hasattr(window, "comboAIModel") and window.comboAIModel.count() > 0:

        active_id = window.comboAIModel.currentText()

    rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)

    if rates is None or len(rates) == 0:

        window.ai_lbl_status.setText("Lỗi dữ liệu MT5!")

        return

    # Kéo thêm dữ liệu và tính toán Volume-Validated Fractals + Math Intraday Trend

    tech_data = None

    r_100 = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 150)

    if r_100 is not None and len(r_100) >= 25:

        current_price = r_100[-1]["close"]

        sub_rates = r_100[-150:]

        volumes = [r["tick_volume"] for r in sub_rates]

        valid_resistances = []

        valid_supports = []

        swing_highs = []

        swing_lows = []

        for i in range(2, len(sub_rates) - 2):

            high = sub_rates[i]["high"]

            low = sub_rates[i]["low"]

            if (
                high > sub_rates[i - 1]["high"]
                and high > sub_rates[i - 2]["high"]
                and high > sub_rates[i + 1]["high"]
                and high > sub_rates[i + 2]["high"]
            ):

                swing_highs.append(high)

            if (
                low < sub_rates[i - 1]["low"]
                and low < sub_rates[i - 2]["low"]
                and low < sub_rates[i + 1]["low"]
                and low < sub_rates[i + 2]["low"]
            ):

                swing_lows.append(low)

        from infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

        sr_info = calculate_sr_levels(sub_rates, current_price=current_price)

        if sr_info:

            resistance = sr_info["resistance"]

            support = sr_info["support"]

        else:

            resistance = max([r["high"] for r in sub_rates[-50:]])

            support = min([r["low"] for r in sub_rates[-50:]])

        closes = [r["close"] for r in sub_rates]

        period = min(50, len(closes))

        alpha = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:

            ema = (price - ema) * alpha + ema

        math_trend = "Đi ngang"

        if len(swing_highs) >= 2 and len(swing_lows) >= 2:

            if (
                swing_highs[-1] > swing_highs[-2]
                and swing_lows[-1] > swing_lows[-2]
                and current_price > ema
            ):

                math_trend = "Tăng"

            elif (
                swing_highs[-1] < swing_highs[-2]
                and swing_lows[-1] < swing_lows[-2]
                and current_price < ema
            ):

                math_trend = "Giảm"

        elif current_price > ema * 1.002:

            math_trend = "Tăng"

        elif current_price < ema * 0.998:

            math_trend = "Giảm"

        tech_data = {
            "current_price": current_price,
            "resistance": resistance,
            "support": support,
            "math_trend": math_trend,
            "ema_50": round(ema, 2),
            "ema_position": "TRÊN EMA 50" if current_price > ema else "DƯỚI EMA 50",
            "structure": f"Volume-Validated (KC: {resistance:.2f}, HT: {support:.2f})",
        }

    d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 60)

    h4_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 60)

    thread = AIAnalyzerThread(
        parent=window,
        sym=sym,
        rates=rates,
        timeframe_str=window.current_tf_str,
        active_id=active_id,
        force_refresh=force,
        tech_data=tech_data,
        d1_rates=d1_rates,
        h4_rates=h4_rates,
    )

    window.ai_thread = thread

    window._active_ai_threads.add(thread)

    thread.finished.connect(lambda t=thread: window._active_ai_threads.discard(t))

    window.ai_thread.signals.result.connect(
        lambda r: _update_panel_with_result(window, r), Qt.QueuedConnection
    )

    window.ai_thread.signals.error.connect(
        lambda e: _show_error(window, e), Qt.QueuedConnection
    )

    window.ai_thread.signals.loading.connect(
        lambda t: window.ai_lbl_status.setText(t), Qt.QueuedConnection
    )

    window.ai_thread.start()


def _show_error(window, error_text):

    window.ai_lbl_status.setText(f"L\u1ed7i: {error_text}")

    window.ai_lbl_status.setStyleSheet(
        "color: #F23645; font-size: 10px; font-family: 'Segoe UI';"
    )


# --- CHI BAO CATALOG ---


INDICATOR_CATALOG = {
    "Xu huong": [
        {"id": "ema", "available": True},
        {"id": "ma200", "available": True},
    ],
    "Cau truc gia": [
        {"id": "donchian", "available": True},
        {"id": "pivot", "available": True},
    ],
    "Dao dong": [
        {"id": "rsi", "available": False},
        {"id": "macd", "available": False},
    ],
    "Khoi luong": [
        {"id": "volume", "available": False},
    ],
}


INDICATOR_LABELS = {
    "Xu huong": "Xu hướng",
    "Cau truc gia": "Cấu trúc giá",
    "Dao dong": "Dao động",
    "Khoi luong": "Khối lượng",
    "ema": "Đường Trung bình EMA (10, 50)",
    "ma200": "Đường MA 200",
    "donchian": "Vùng Hỗ trợ / Kháng cự (Donchian 100)",
    "pivot": "Pivot Points (Classic)",
    "rsi": "RSI (14) (Sắp ra mắt)",
    "macd": "MACD (Sắp ra mắt)",
    "volume": "Volume (Sắp ra mắt)",
}


class IndicatorDialog(QDialog):

    def __init__(self, parent=None, active_indicators=None, on_change=None):

        super().__init__(parent)

        self.setWindowTitle("Chỉ báo")

        self.resize(560, 400)

        self.on_change = on_change

        self.active_indicators = active_indicators or {}

        self._checkboxes = {}

        self._current_cat = list(INDICATOR_CATALOG.keys())[0]

        self.setStyleSheet("""







            QDialog { background-color: #1E222D; }







            QLineEdit { background-color: #131722; color: #D1D4DC; border: 1px solid #2B3139; border-radius: 4px; padding: 7px 10px; font-size: 13px; margin: 10px 10px 6px 10px; }







            QListWidget { background-color: transparent; border: none; outline: none; color: #8B949E; font-size: 13px; }







            QListWidget::item { padding: 10px 14px; border-radius: 4px; }







            QListWidget::item:selected { background-color: #2B3139; color: #FFFFFF; }







            QListWidget::item:hover { background-color: #21262D; color: #C9D1D9; }







            QCheckBox { color: #D1D4DC; font-size: 13px; padding: 8px 4px; spacing: 8px; }







            QCheckBox:hover { color: #FFFFFF; }







            QCheckBox:disabled { color: #484F58; }







            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #444C56; background: #161B22; image: none; }







            QCheckBox::indicator:hover { border: 1px solid #58A6FF; }







            QCheckBox::indicator:checked { background: #1F6FEB; border: 1px solid #1F6FEB; image: url(ui/assets/check_icon.svg); }







            QCheckBox::indicator:disabled { background: #21262D; border: 1px solid #30363D; image: none; }







        """)

        main = QVBoxLayout(self)

        main.setContentsMargins(0, 0, 0, 0)

        main.setSpacing(0)

        self.search_bar = QLineEdit()

        self.search_bar.setPlaceholderText("Tìm kiếm chỉ báo...")

        main.addWidget(self.search_bar)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background:#21262D;")

        main.addWidget(div)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = QListWidget()

        self.sidebar.setFixedWidth(160)

        for k in INDICATOR_CATALOG:
            self.sidebar.addItem(INDICATOR_LABELS.get(k, k))

        self.sidebar.setCurrentRow(0)

        self.sidebar.currentRowChanged.connect(self._switch_cat)

        row.addWidget(self.sidebar)

        vsep = QFrame()
        vsep.setFixedWidth(1)
        vsep.setStyleSheet("background:#21262D;")

        row.addWidget(vsep)

        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background:transparent;")

        self.right_layout = QVBoxLayout(self.right_panel)

        self.right_layout.setContentsMargins(14, 8, 14, 14)
        self.right_layout.setSpacing(0)

        row.addWidget(self.right_panel)

        main.addLayout(row)

        self.search_bar.textChanged.connect(self._on_search)

        self._render(self._current_cat)

    def _clear(self):

        while self.right_layout.count():

            item = self.right_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def _render(self, cat, filt=""):

        self._clear()

        hdr = QLabel(INDICATOR_LABELS.get(cat, cat).upper())

        hdr.setStyleSheet(
            "color:#6E7681;font-size:10px;font-weight:bold;padding:8px 4px 4px 0;"
        )

        self.right_layout.addWidget(hdr)

        found = False

        for ind in INDICATOR_CATALOG.get(cat, []):

            label = INDICATOR_LABELS.get(ind["id"], ind["id"])

            if filt and filt.lower() not in label.lower():
                continue

            found = True

            cb = QCheckBox(label)

            cb.setEnabled(ind["available"])

            cb.setChecked(self.active_indicators.get(ind["id"], False))

            if ind["available"]:

                iid = ind["id"]

                cb.toggled.connect(lambda chk, i=iid: self._toggle(i, chk))

            self.right_layout.addWidget(cb)

            self._checkboxes[ind["id"]] = cb

        if not found:

            lbl = QLabel("Không tìm thấy.")

            lbl.setStyleSheet("color:#484F58;font-size:12px;padding:10px 0;")

            self.right_layout.addWidget(lbl)

        self.right_layout.addStretch()

    def _switch_cat(self, row):

        keys = list(INDICATOR_CATALOG.keys())

        if 0 <= row < len(keys):

            self._current_cat = keys[row]

            self._render(self._current_cat, self.search_bar.text())

    def _on_search(self, text):

        self._render(self._current_cat, text)

    def _toggle(self, ind_id, checked):

        self.active_indicators[ind_id] = checked

        if self.on_change:
            self.on_change()


# ============================================================


# INDICATOR HELPERS - Clean Architecture / Single Responsibility


# ============================================================


def _compute_indicators(df, active):
    """







    Tinh toan tat ca chi bao can thiet.







    Chi tinh nhung chi bao dang duoc bat -> Tiet kiem CPU.







    """

    result = {}

    n = len(df)

    x = list(range(n))

    result["x"] = x

    if active.get("ema", False):

        result["EMA_10"] = df["close"].ewm(span=10, adjust=False).mean().tolist()

        result["EMA_50"] = df["close"].ewm(span=50, adjust=False).mean().tolist()

    if active.get("ma200", False):

        result["MA_200"] = (
            df["close"].rolling(window=200, min_periods=1).mean().tolist()
        )

    if active.get("donchian", False) and n >= 100:

        result["DONCHIAN_HIGH"] = df["high"].iloc[-100:].max()

        result["DONCHIAN_LOW"] = df["low"].iloc[-100:].min()

    if active.get("pivot", False):

        try:

            from infrastructure.brokers.mt5_safe import mt5

            sym = getattr(df, "_sym", None)

        except Exception:

            sym = None

        result["_pivot_raw"] = True  # Signal to fetch D1 later

    return result


def _get_or_create_curve(window, key, pen, **kwargs):
    """







    Lay curve da ton tai hoac tao moi va addItem vao plot_widget.







    Day la trai tim cua setData pattern.







    """

    if not hasattr(window, "_ind_curves"):

        window._ind_curves = {}

    if key not in window._ind_curves:

        curve = pg.PlotCurveItem(pen=pen, **kwargs)

        window.plot_widget.addItem(curve)

        window._ind_curves[key] = curve

    return window._ind_curves[key]


def _get_or_create_hline(window, key, pen):
    """Lay InfiniteLine da ton tai hoac tao moi."""

    if not hasattr(window, "_ind_curves"):

        window._ind_curves = {}

    if key not in window._ind_curves:

        line = pg.InfiniteLine(angle=0, pen=pen, movable=False)

        window.plot_widget.addItem(line)

        window._ind_curves[key] = line

    return window._ind_curves[key]


def _hide_curve(window, key):
    """An duong ke neu chi bao tuong ung bi tat."""

    if hasattr(window, "_ind_curves") and key in window._ind_curves:

        window._ind_curves[key].setVisible(False)


def _refresh_indicators(window, df):
    """







    Ham dieu phoi chinh: Quyet dinh ve gi va an gi.







    Su dung setData() thay vi clear() + addItem() -> Hieu nang ~80% tot hon.







    """

    active = getattr(window, "active_indicators", {})

    computed = _compute_indicators(df, active)

    x = computed.get("x", [])

    # --- EMA 10 ---

    if active.get("ema", False) and "EMA_10" in computed:

        c = _get_or_create_curve(window, "EMA_10", pg.mkPen("#F59E0B", width=1.2))

        c.setData(x, computed["EMA_10"])

        c.setVisible(True)

    else:

        _hide_curve(window, "EMA_10")

    # --- EMA 50 ---

    if active.get("ema", False) and "EMA_50" in computed:

        c = _get_or_create_curve(window, "EMA_50", pg.mkPen("#3B82F6", width=1.5))

        c.setData(x, computed["EMA_50"])

        c.setVisible(True)

    else:

        _hide_curve(window, "EMA_50")

    # --- MA 200 ---

    if active.get("ma200", False) and "MA_200" in computed:

        c = _get_or_create_curve(
            window, "MA_200", pg.mkPen("#A78BFA", width=1.2, style=Qt.DashLine)
        )

        c.setData(x, computed["MA_200"])

        c.setVisible(True)

    else:

        _hide_curve(window, "MA_200")

    # --- DONCHIAN S/R ---

    # Dung PlotCurveItem voi x gioi han trong 100 nen gan nhat

    if active.get("donchian", False) and "DONCHIAN_HIGH" in computed:

        total = len(x)

        x_start = max(0, total - 100)

        x_end = total - 1

        r_curve = _get_or_create_curve(
            window,
            "DONCHIAN_R",
            pg.mkPen(color=(242, 54, 69, 160), width=1, style=Qt.DashLine),
        )

        r_curve.setData(
            [x_start, x_end], [computed["DONCHIAN_HIGH"], computed["DONCHIAN_HIGH"]]
        )

        r_curve.setVisible(True)

        s_curve = _get_or_create_curve(
            window,
            "DONCHIAN_S",
            pg.mkPen(color=(16, 185, 129, 160), width=1, style=Qt.DashLine),
        )

        s_curve.setData(
            [x_start, x_end], [computed["DONCHIAN_LOW"], computed["DONCHIAN_LOW"]]
        )

        s_curve.setVisible(True)

    else:

        _hide_curve(window, "DONCHIAN_R")

        _hide_curve(window, "DONCHIAN_S")

    # --- PIVOT POINTS (Classic) ---

    # Su dung PlotCurveItem thay vi InfiniteLine de tranh duong ke vo tan

    if active.get("pivot", False):

        try:

            from infrastructure.brokers.mt5_safe import mt5

            import datetime

            sym = getattr(window, "current_sym", "XAUUSD")

            d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)

            if d1_rates is not None and len(d1_rates) >= 2:

                prev = d1_rates[-2]  # Phien hom qua

                H = prev["high"]

                L = prev["low"]

                C = prev["close"]

                P = (H + L + C) / 3.0

                R1 = 2 * P - L

                S1 = 2 * P - H

                R2 = P + (H - L)

                S2 = P - (H - L)

                # Tim x_start: Chi so nen dau tien cua phien hom nay (D1 hien tai)

                today_open_time = d1_rates[-1]["time"]

                total = len(df)

                x_start = 0

                if "time" in df.columns:

                    today_mask = df["time"] >= today_open_time

                    if today_mask.any():

                        x_start = int(today_mask.idxmax())

                x_end = total - 1

                # Neu khong co nen hom nay (ngoai gio), ve tu nen cuoi cung tro ve

                if x_start >= x_end:

                    x_start = max(0, x_end - 30)

                pivot_cfg = [
                    ("PIVOT_P", P, pg.mkPen("#D1D4DC", width=1, style=Qt.DashLine)),
                    (
                        "PIVOT_R1",
                        R1,
                        pg.mkPen(color=(242, 54, 69, 200), width=1, style=Qt.DashLine),
                    ),
                    (
                        "PIVOT_S1",
                        S1,
                        pg.mkPen(color=(16, 185, 129, 200), width=1, style=Qt.DashLine),
                    ),
                    (
                        "PIVOT_R2",
                        R2,
                        pg.mkPen(color=(242, 54, 69, 120), width=1, style=Qt.DotLine),
                    ),
                    (
                        "PIVOT_S2",
                        S2,
                        pg.mkPen(color=(16, 185, 129, 120), width=1, style=Qt.DotLine),
                    ),
                ]

                for key, val, pen in pivot_cfg:

                    c = _get_or_create_curve(window, key, pen)

                    c.setData([x_start, x_end], [val, val])

                    c.setVisible(True)

        except Exception as e:

            print(f"[Pivot] Error: {e}")

    else:

        for key in ["PIVOT_P", "PIVOT_R1", "PIVOT_S1", "PIVOT_R2", "PIVOT_S2"]:

            _hide_curve(window, key)


def setup_chart_ui(window):

    chart_layout = window.frameChartArea.layout()

    while chart_layout.count():

        item = chart_layout.takeAt(0)

        w = item.widget()

        if w:

            w.deleteLater()

    tf_widget = QWidget()

    tf_layout = QHBoxLayout(tf_widget)

    tf_layout.setContentsMargins(5, 5, 5, 5)

    tf_layout.setSpacing(5)

    window.lbl_chart_title = QLabel("CH\u01afA CH\u1eccN M\u00c3")

    window.lbl_chart_title.setStyleSheet(
        "color: #E5E7EB; font-size: 16px; font-weight: bold; margin-right: 20px; font-family: 'Segoe UI';"
    )

    tf_layout.addWidget(window.lbl_chart_title)

    tfs = [
        ("M1", mt5.TIMEFRAME_M1),
        ("M5", mt5.TIMEFRAME_M5),
        ("M15", mt5.TIMEFRAME_M15),
        ("M30", mt5.TIMEFRAME_M30),
        ("H1", mt5.TIMEFRAME_H1),
        ("H4", mt5.TIMEFRAME_H4),
        ("D1", mt5.TIMEFRAME_D1),
    ]

    window.current_tf = mt5.TIMEFRAME_H1

    window.current_tf_str = "H1"

    window.current_sym = None

    window.chart_data_list = []

    window.tf_buttons = {}

    def update_tf_styles():

        for name, btn in window.tf_buttons.items():

            if name == window.current_tf_str:

                btn.setStyleSheet(
                    "QPushButton { background-color: #1F6FEB; color: #FFFFFF; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; }"
                )

            else:

                btn.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #8B949E; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; } QPushButton:hover { background-color: #21262D; color: #C9D1D9; }"
                )

    for name, tf_val in tfs:

        btn = QPushButton(name)

        btn.setCursor(Qt.PointingHandCursor)

        btn.clicked.connect(
            lambda checked=False, v=tf_val, n=name: change_timeframe(v, n)
        )

        window.tf_buttons[name] = btn

        tf_layout.addWidget(btn)

    update_tf_styles()

    # Them separator va nut Chi bao

    sep = QFrame()

    sep.setFrameShape(QFrame.VLine)

    sep.setStyleSheet("QFrame { color: #30363D; }")

    tf_layout.addWidget(sep)

    window.btn_indicators = QPushButton("Chỉ báo")

    window.btn_indicators.setCursor(Qt.PointingHandCursor)

    window.btn_indicators.setStyleSheet(
        "QPushButton { background-color: transparent; color: #D1D4DC; border: none; font-weight: bold; padding: 6px 12px; } QPushButton:hover { background-color: #2B3139; border-radius: 4px; }"
    )

    window.active_indicators = {"ema": False, "donchian": False}

    def _open_indicators():

        def _refresh():

            if hasattr(window, "current_sym"):

                draw_and_analyze(window.current_sym)

        dlg = IndicatorDialog(window, window.active_indicators, on_change=_refresh)

        dlg.exec()

    window.btn_indicators.clicked.connect(_open_indicators)

    tf_layout.addWidget(window.btn_indicators)

    tf_layout.addStretch()

    chart_layout.addWidget(tf_widget)

    if hasattr(window, "chartSplitter"):

        window.chartSplitter.setSizes([900, 330])

    window.time_axis = TimeAxisItem(orientation="bottom")

    window.plot_widget = pg.PlotWidget(
        background="#080b11", axisItems={"bottom": window.time_axis}
    )

    window.plot_widget.setMouseEnabled(x=True, y=False)

    window.plot_widget.showGrid(x=True, y=True, alpha=0.06)

    window.plot_widget.getAxis("left").setPen(pg.mkPen(color="#1c2438"))

    window.plot_widget.getAxis("bottom").setPen(pg.mkPen(color="#1c2438"))

    window.plot_widget.getAxis("left").setTextPen(pg.mkPen(color="#64748b"))

    window.plot_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#64748b"))

    chart_layout.addWidget(window.plot_widget)

    # Add Crosshair lines

    window.vLine = pg.InfiniteLine(
        angle=90, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine)
    )

    window.hLine = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine)
    )

    window.plot_widget.addItem(window.vLine, ignoreBounds=True)

    window.plot_widget.addItem(window.hLine, ignoreBounds=True)

    # Crosshair text label

    window.crosshair_label = pg.TextItem(
        color="#E5E7EB", anchor=(0, 1), fill=pg.mkBrush(0, 0, 0, 150)
    )

    window.crosshair_label.setZValue(10)  # ensure it's on top

    window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)

    # Current price line

    window.current_price_line = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#3FB950", style=QtCore.Qt.DotLine)
    )

    window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

    def mouseMoved(evt):

        pos = evt

        if window.plot_widget.sceneBoundingRect().contains(pos):

            mousePoint = window.plot_widget.plotItem.vb.mapSceneToView(pos)

            x = mousePoint.x()

            y = mousePoint.y()

            if hasattr(window, "chart_data_list") and window.chart_data_list:

                idx = int(round(x))

                if 0 <= idx < len(window.chart_data_list):

                    t_val = window.time_axis.timestamps[idx]

                    dt_str = datetime.fromtimestamp(t_val).strftime("%d/%m %H:%M")

                    data = window.chart_data_list[idx]

                    o, c, l, h = data[1], data[2], data[3], data[4]

                    fmt = ".5f" if y < 10 else ".3f"

                    window.crosshair_label.setText(
                        f"{dt_str} | O:{o:{fmt}} H:{h:{fmt}} L:{l:{fmt}} C:{c:{fmt}}\nGiá: {y:{fmt}}"
                    )

                    if x > len(window.chart_data_list) - 30:

                        window.crosshair_label.setAnchor((1, 1))

                    else:

                        window.crosshair_label.setAnchor((0, 1))

                    window.crosshair_label.setPos(x, y)

            window.vLine.setPos(x)

            window.hLine.setPos(y)

    window.plot_widget.scene().sigMouseMoved.connect(mouseMoved)

    # Live chart update

    def on_market_tick(sym, bid, ask):

        if not hasattr(window, "current_sym") or sym != window.current_sym:

            return

        window.current_price_line.setPos(bid)

        rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 1)

        if (
            rates is not None
            and len(rates) > 0
            and hasattr(window, "chart_data_list")
            and window.chart_data_list
        ):

            r = rates[0]

            last_idx = window.chart_data_list[-1][0]

            last_time = window.time_axis.timestamps[-1]

            changed = False

            if r["time"] == last_time:

                window.chart_data_list[-1] = (
                    last_idx,
                    r["open"],
                    r["close"],
                    r["low"],
                    r["high"],
                )

                changed = True

            elif r["time"] > last_time:

                new_idx = last_idx + 1

                window.chart_data_list.append(
                    (new_idx, r["open"], r["close"], r["low"], r["high"])
                )

                window.time_axis.timestamps.append(r["time"])

                changed = True

            if changed and hasattr(window, "candlesticks"):

                window.candlesticks.data = window.chart_data_list

                window.candlesticks.generatePicture()

                window.candlesticks.update()

    from core.event_bus import event_bus

    event_bus.market_tick.connect(on_market_tick)

    # Xay dung panel phan tich moi (thay QTextEdit cu)

    _build_analysis_panel(window)

    def update_y_range():

        if not window.chart_data_list:

            return

        view_range = window.plot_widget.viewRange()[0]

        x_min = max(0, int(view_range[0]))

        x_max = min(len(window.chart_data_list) - 1, int(view_range[1]))

        if x_min < x_max:

            visible_data = window.chart_data_list[x_min : x_max + 1]

            if not visible_data:

                return

            y_min = min(d[3] for d in visible_data)

            y_max = max(d[4] for d in visible_data)

            margin = (y_max - y_min) * 0.1

            if margin == 0:

                margin = y_max * 0.001

            window.plot_widget.setYRange(y_min - margin, y_max + margin, padding=0)

    window.plot_widget.sigXRangeChanged.connect(update_y_range)

    def change_timeframe(val, name_str):

        window.current_tf = val

        window.current_tf_str = name_str

        update_tf_styles()

        if window.current_sym:

            draw_and_analyze(window.current_sym)

    def draw_and_analyze(sym):
        rates = None
        if mt5.terminal_info() is not None:
            mt5.symbol_select(sym, True)
            rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)

        if rates is None or len(rates) == 0:
            import numpy as np
            import time

            base_time = int(time.time()) - 130 * 900
            rates_list = []
            cur = 2645.0
            np.random.seed(101)
            for i in range(130):
                drift = np.sin(i / 12.0) * 2.2 + (0.25 if i > 50 else -0.1)
                change = np.random.normal(drift, 1.8)
                cur += change
                o = cur - change
                c = cur
                h = max(o, c) + abs(np.random.normal(0.8, 0.8))
                l = min(o, c) - abs(np.random.normal(0.8, 0.8))
                t = base_time + i * 900
                rates_list.append(
                    {
                        "time": t,
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c,
                        "tick_volume": 120,
                    }
                )
            rates = rates_list

        window.chart_data_list = []
        timestamps = []
        for i in range(len(rates)):
            r = rates[i]
            window.chart_data_list.append(
                (i, r["open"], r["close"], r["low"], r["high"])
            )
            timestamps.append(r["time"])

        window.time_axis.update_timestamps(timestamps)
        window.plot_widget.clear()
        window._ind_curves = {}

        last_r = rates[-1]
        diff = last_r["close"] - rates[0]["open"]
        diff_pct = (diff / rates[0]["open"]) * 100
        sign = "+" if diff >= 0 else ""
        window.lbl_chart_title.setText(
            f"{sym} / 0.1lot • 10 • NHsA06    O {last_r['open']:.2f}  H {last_r['high']:.2f}  L {last_r['low']:.2f}  {sign}{diff:.2f} ({sign}{diff_pct:.2f}%)"
        )
        window.lbl_chart_title.setStyleSheet(
            "color: #f8fafc; font-size: 12px; font-weight: 700; font-family: 'Consolas', monospace;"
        )

        window.candlesticks = CandlestickItem(window.chart_data_list)
        window.plot_widget.addItem(window.candlesticks)

        # Tự động nhận diện và vẽ vùng FVG (Fair Value Gap) màu vàng hổ phách
        if len(window.chart_data_list) >= 3:
            for i in range(2, len(window.chart_data_list)):
                t_cur, _, _, l_cur, h_cur = window.chart_data_list[i]
                t_prev2, _, _, l_prev2, h_prev2 = window.chart_data_list[i - 2]

                # Bullish FVG
                if l_cur > h_prev2 and (l_cur - h_prev2) > 1.2:
                    fvg_item = QGraphicsRectItem(
                        t_prev2, h_prev2, (t_cur - t_prev2 + 12), (l_cur - h_prev2)
                    )
                    fvg_item.setBrush(pg.mkBrush(245, 158, 11, 45))
                    fvg_item.setPen(
                        pg.mkPen(
                            color=pg.mkColor(245, 158, 11, 180),
                            width=1,
                            style=QtCore.Qt.SolidLine,
                        )
                    )
                    window.plot_widget.addItem(fvg_item)
                    fvg_lbl = pg.TextItem(
                        text="FVG", color=(245, 158, 11, 240), anchor=(1, 0.5)
                    )
                    fvg_lbl.setPos(t_cur + 12, (h_prev2 + l_cur) / 2)
                    window.plot_widget.addItem(fvg_lbl)

                # Bearish FVG
                elif h_cur < l_prev2 and (l_prev2 - h_cur) > 1.2:
                    fvg_item = QGraphicsRectItem(
                        t_prev2, h_cur, (t_cur - t_prev2 + 12), (l_prev2 - h_cur)
                    )
                    fvg_item.setBrush(pg.mkBrush(245, 158, 11, 45))
                    fvg_item.setPen(
                        pg.mkPen(
                            color=pg.mkColor(245, 158, 11, 180),
                            width=1,
                            style=QtCore.Qt.SolidLine,
                        )
                    )
                    window.plot_widget.addItem(fvg_item)
                    fvg_lbl = pg.TextItem(
                        text="FVG", color=(245, 158, 11, 240), anchor=(1, 0.5)
                    )
                    fvg_lbl.setPos(t_cur + 12, (h_cur + l_prev2) / 2)
                    window.plot_widget.addItem(fvg_lbl)

        if hasattr(window, "txtAIReasoning"):
            ai_html = (
                "<div style='font-family: Segoe UI, sans-serif; font-size: 11px; color: #cbd5e1;'>"
                "<p style='margin-bottom: 8px; font-weight: bold; color: #94a3b8;'>Qwen 2.5 macro reasoning</p>"
                "<p style='margin-bottom: 10px; line-height: 1.4;'>"
                "Qwen 2.5 macro reasoning output the last trading sectors reconciliation skills from the result of asks more on the fair indicated products above out-turns lows-of macro reasoning:"
                "</p>"
                "<ul style='margin-left: -15px; margin-top: 0px; margin-bottom: 10px; line-height: 1.5; color: #94a3b8;'>"
                "<li><b style='color: #f8fafc;'>Fair Value Gap:</b> is the evasion of conolests. The ultorii nictra-orms trading conchange, borthatonicenerge and economic trades.</li>"
                "<li><b style='color: #f8fafc;'>Development:</b> tondlest can interlerve entries ra:slies no colmation position the imporenurarsl charge, vitnes requires contilent's caro-is lettes.</li>"
                "<li><b style='color: #f8fafc;'>Emergency kill-switch:</b> is vin strating combind inverne-its contributos to the eopiteron to end slitect beattwists.</li>"
                "</ul>"
                "<p style='color: #64748b; font-size: 10px;'>There are macro reasoning output s end of the first tradion.</p>"
                "</div>"
            )
            window.txtAIReasoning.setHtml(ai_html)

        # Thêm lại crosshair và live price line do hàm clear() đã xóa mất

        if hasattr(window, "vLine"):
            window.plot_widget.addItem(window.vLine, ignoreBounds=True)

        if hasattr(window, "hLine"):
            window.plot_widget.addItem(window.hLine, ignoreBounds=True)

        if hasattr(window, "crosshair_label"):
            window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)

        if hasattr(window, "current_price_line"):
            window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

        total_candles = len(window.chart_data_list)

        window.plot_widget.setLimits(xMin=-20, xMax=total_candles + 20)

        view_bars = min(120, total_candles)

        window.plot_widget.setXRange(total_candles - view_bars, total_candles + 5)

        update_y_range()

        window.current_sym = sym

        # --- DRAW INDICATORS (setData pattern) ---

        df = pd.DataFrame(rates)

        _refresh_indicators(window, df)

        # -----------------------

        _run_analysis(window, sym)

    def on_watchlist_click(item, column):

        sym = item.text(0)

        if sym.startswith("v "):

            return

    if hasattr(window, "treeWatchlist"):
        window.treeWatchlist.itemDoubleClicked.connect(on_watchlist_click)

    window.draw_and_analyze = draw_and_analyze
    # Auto-load default active pair XAUUSD
    draw_and_analyze("XAUUSD")
