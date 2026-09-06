
import pyqtgraph as pg
from PySide6 import QtCore
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPicture, QPainter
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton,
                                QWidget, QLabel, QFrame, QScrollArea)
from core.mt5_safe import mt5
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
                strings.append(dt.strftime('%d/%m %H:%M'))
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
        p.setPen(pg.mkPen('w'))
        w = 0.35
        for (t, open, close, low, high) in self.data:
            if open > close:
                p.setBrush(pg.mkBrush('#F23645'))
                p.setPen(pg.mkPen('#F23645'))
            else:
                p.setBrush(pg.mkBrush('#089981'))
                p.setPen(pg.mkPen('#089981'))
            p.drawLine(QPointF(t, low), QPointF(t, high))
            min_price = open if open < close else close
            p.drawRect(QtCore.QRectF(t-w, min_price, w*2, max(abs(close-open), 0.0001)))
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
    def __init__(self, sym, rates, timeframe_str, active_id, force_refresh=False, tech_data=None, d1_rates=None, h4_rates=None):
        super().__init__()
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
            from core.ai.analysis_engine import AnalysisEngine
            from core.ai.decision_gate import DecisionGate
            model_name = self.active_id if self.active_id else 'qwen2.5'
            engine = AnalysisEngine(model_name=model_name)

            if self.is_cancelled:
                return

            self.signals.loading.emit('\u0110ang t\u1ed5ng h\u1ee3p d\u1eef li\u1ec7u...')
            result = engine.analyze(self.sym, tech_data=self.tech_data)

            if self.is_cancelled:
                return

            if 'error' in result:
                self.signals.error.emit(str(result['error']))
                return

            # Dinh kem them gia va S/R tu cache hoac tech_data
            cached = engine.cache.get(self.sym, {})
            result['_price'] = cached.get('result', result).get('_price', 0)
            result['_resistance'] = cached.get('resistance', 0)
            result['_support'] = cached.get('support', 0)

            if self.tech_data:
                result['_price'] = self.tech_data['current_price']
                result['_resistance'] = self.tech_data['resistance']
                result['_support'] = self.tech_data['support']

            # Them HTF bias va vi tri gia vao result
            try:
                gate = DecisionGate()
                # Truyen 100 nen cuoi cung tu self.rates neu co
                rates_for_pos = self.rates[-100:] if self.rates is not None and len(self.rates) >= 100 else self.rates
                price_info = gate._get_price_position(self.sym, rates=rates_for_pos)
                htf_bias = gate._get_htf_bias(self.sym, d1_rates=self.d1_rates, h4_rates=self.h4_rates)
                if price_info:
                    result['_position'] = price_info['position']
                    result['_pct_support'] = price_info.get('pct_from_support', 0)
                    result['_pct_resistance'] = price_info.get('pct_from_resistance', 0)
                result['_htf_bias'] = htf_bias
            except Exception:
                pass

            self.signals.result.emit(result)

        except Exception as e:
            if not self.is_cancelled:
                self.signals.error.emit(str(e))


def _make_separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setStyleSheet('background-color: #21262D; max-height: 1px;')
    return sep


def _make_label(text, color='#8B949E', size=11, bold=False, font='Segoe UI'):
    lbl = QLabel(text)
    weight = 'bold' if bold else 'normal'
    lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {weight}; font-family: '{font}';")
    lbl.setWordWrap(True)
    return lbl


def _build_analysis_panel(window):
    """Xay dung panel phan tich bang QWidget thuan tuy (khong dung QTextEdit)."""
    ai_layout = window.frameAIArea.layout()
    while ai_layout.count():
        item = ai_layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()

    # Scroll area de cuon khi noi dung dai
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        'QScrollArea { border: none; background: #010409; }'
        'QScrollBar:vertical { background: #010409; width: 6px; }'
        'QScrollBar::handle:vertical { background: #30363D; border-radius: 3px; }'
        'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }'
    )

    container = QWidget()
    container.setStyleSheet('background: #010409;')
    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(14, 14, 14, 14)
    vbox.setSpacing(8)

    # Header
    window.ai_lbl_header = _make_label('PH\u00c2N T\u00cdCH', '#E5E7EB', 16, True)
    vbox.addWidget(window.ai_lbl_header)

    window.ai_lbl_time = _make_label('Ch\u01b0a ph\u00e2n t\u00edch', '#58A6FF', 10)
    vbox.addWidget(window.ai_lbl_time)

    vbox.addWidget(_make_separator())

    # Gia / KC / HT
    price_frame = QFrame()
    price_frame.setStyleSheet('QFrame { background: #161B22; border: 1px solid #30363D; border-radius: 4px; }')
    pfl = QVBoxLayout(price_frame)
    pfl.setContentsMargins(10, 8, 10, 8)
    pfl.setSpacing(4)

    window.ai_lbl_price = _make_label('--', '#E5E7EB', 20, True, 'Consolas')
    pfl.addWidget(window.ai_lbl_price)

    # KC row
    kc_row = QHBoxLayout()
    kc_row.addWidget(_make_label('KC', '#8B949E', 10, True))
    window.ai_lbl_resistance = _make_label('--', '#F23645', 12, True, 'Consolas')
    window.ai_lbl_resistance.setAlignment(Qt.AlignRight)
    kc_row.addWidget(window.ai_lbl_resistance)
    window.ai_lbl_res_delta = _make_label('', '#F23645', 10, False, 'Consolas')
    window.ai_lbl_res_delta.setAlignment(Qt.AlignRight)
    window.ai_lbl_res_delta.setFixedWidth(70)
    kc_row.addWidget(window.ai_lbl_res_delta)
    pfl.addLayout(kc_row)

    # HT row
    ht_row = QHBoxLayout()
    ht_row.addWidget(_make_label('HT', '#8B949E', 10, True))
    window.ai_lbl_support = _make_label('--', '#3FB950', 12, True, 'Consolas')
    window.ai_lbl_support.setAlignment(Qt.AlignRight)
    ht_row.addWidget(window.ai_lbl_support)
    window.ai_lbl_sup_delta = _make_label('', '#3FB950', 10, False, 'Consolas')
    window.ai_lbl_sup_delta.setAlignment(Qt.AlignRight)
    window.ai_lbl_sup_delta.setFixedWidth(70)
    ht_row.addWidget(window.ai_lbl_sup_delta)
    pfl.addLayout(ht_row)

    vbox.addWidget(price_frame)

    vbox.addWidget(_make_separator())

    # Xu huong Macro
    macro_row = QHBoxLayout()
    macro_row.addWidget(_make_label('V\u0128 M\u00d4', '#8B949E', 11, True))
    window.ai_lbl_macro = _make_label('--', '#8B949E', 13, True)
    window.ai_lbl_macro.setAlignment(Qt.AlignRight)
    macro_row.addWidget(window.ai_lbl_macro)
    vbox.addLayout(macro_row)

    # HTF Bias (D1 + H4)
    htf_row = QHBoxLayout()
    htf_row.addWidget(_make_label('D1 + H4', '#8B949E', 11, True))
    window.ai_lbl_htf = _make_label('--', '#8B949E', 13, True)
    window.ai_lbl_htf.setAlignment(Qt.AlignRight)
    htf_row.addWidget(window.ai_lbl_htf)
    vbox.addLayout(htf_row)

    # Xu huong Intraday
    intra_row = QHBoxLayout()
    intra_row.addWidget(_make_label('NG\u1eaeN H\u1ea0N', '#8B949E', 11, True))
    window.ai_lbl_intraday = _make_label('--', '#8B949E', 13, True)
    window.ai_lbl_intraday.setAlignment(Qt.AlignRight)
    intra_row.addWidget(window.ai_lbl_intraday)
    vbox.addLayout(intra_row)

    # Vi tri gia
    pos_row = QHBoxLayout()
    pos_row.addWidget(_make_label('V\u1eca TR\u00cd', '#8B949E', 11, True))
    window.ai_lbl_position = _make_label('--', '#8B949E', 13, True)
    window.ai_lbl_position.setAlignment(Qt.AlignRight)
    pos_row.addWidget(window.ai_lbl_position)
    vbox.addLayout(pos_row)

    vbox.addWidget(_make_separator())

    # Kich ban chinh
    sa_frame = QFrame()
    sa_frame.setStyleSheet('QFrame { background: #0D1117; border: 1px solid #21262D; border-left: 3px solid #3FB950; border-radius: 2px; }')
    sa_layout = QVBoxLayout(sa_frame)
    sa_layout.setContentsMargins(10, 8, 10, 8)
    sa_layout.setSpacing(4)
    sa_layout.addWidget(_make_label('K\u1ecaCH B\u1ea2N CH\u00cdNH', '#8B949E', 10, True))
    window.ai_lbl_scenario_a = _make_label('--', '#C9D1D9', 12)
    sa_layout.addWidget(window.ai_lbl_scenario_a)
    vbox.addWidget(sa_frame)

    # Kich ban phu
    sb_frame = QFrame()
    sb_frame.setStyleSheet('QFrame { background: #0D1117; border: 1px solid #21262D; border-left: 3px solid #F23645; border-radius: 2px; }')
    sb_layout = QVBoxLayout(sb_frame)
    sb_layout.setContentsMargins(10, 8, 10, 8)
    sb_layout.setSpacing(4)
    sb_layout.addWidget(_make_label('K\u1ecaCH B\u1ea2N PH\u1ee4', '#8B949E', 10, True))
    window.ai_lbl_scenario_b = _make_label('--', '#C9D1D9', 12)
    sb_layout.addWidget(window.ai_lbl_scenario_b)
    vbox.addWidget(sb_frame)

    vbox.addSpacing(6)

    # Nut phan tich lai
    btn_refresh = QPushButton('Ph\u00e2n t\u00edch l\u1ea1i')
    btn_refresh.setCursor(Qt.PointingHandCursor)
    btn_refresh.setStyleSheet(
        'QPushButton { background: transparent; color: #58A6FF; border: 1px solid #30363D;'
        ' border-radius: 4px; padding: 6px; font-size: 11px; font-weight: bold; }'
        'QPushButton:hover { background: #161B22; }'
    )
    btn_refresh.clicked.connect(lambda: _force_reanalyze(window))
    vbox.addWidget(btn_refresh)

    # Status
    window.ai_lbl_status = _make_label('Nh\u1ea5p \u0111\u00fap m\u1ed9t m\u00e3 \u1edf Watchlist \u0111\u1ec3 ph\u00e2n t\u00edch.', '#8B949E', 10)
    window.ai_lbl_status.setAlignment(Qt.AlignCenter)
    vbox.addWidget(window.ai_lbl_status)

    vbox.addStretch()

    scroll.setWidget(container)
    ai_layout.addWidget(scroll)


def _force_reanalyze(window):
    if window.current_sym:
        _run_analysis(window, window.current_sym, force=True)


def _update_panel_with_result(window, result):
    """Cap nhat tat ca cac QLabel tren panel tu dict ket qua AI."""
    now_str = datetime.now().strftime('%H:%M %d/%m/%Y')
    window.ai_lbl_time.setText(f'C\u1eadp nh\u1eadt: {now_str}')

    price = result.get('_price', 0)
    res = result.get('_resistance', 0)
    sup = result.get('_support', 0)

    if price > 0:
        window.ai_lbl_price.setText(f'{price:,.2f}')
    if res > 0:
        window.ai_lbl_resistance.setText(f'{res:,.2f}')
        delta_r = res - price if price > 0 else 0
        window.ai_lbl_res_delta.setText(f'+{delta_r:,.2f}')
    if sup > 0:
        window.ai_lbl_support.setText(f'{sup:,.2f}')
        delta_s = sup - price if price > 0 else 0
        window.ai_lbl_sup_delta.setText(f'{delta_s:,.2f}')

    # Xu huong
    macro_trend = result.get('trend_macro', '--')
    intra_trend = result.get('trend_intraday', '--')

    def _trend_color(trend_text):
        t = trend_text.lower()
        if 't\u0103ng' in t or 'bullish' in t or 'tang' in t:
            return '#3FB950'
        elif 'gi\u1ea3m' in t or 'bearish' in t or 'giam' in t:
            return '#F23645'
        return '#8B949E'

    window.ai_lbl_macro.setText(macro_trend)
    window.ai_lbl_macro.setStyleSheet(f"color: {_trend_color(macro_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';")

    window.ai_lbl_intraday.setText(intra_trend)
    window.ai_lbl_intraday.setStyleSheet(f"color: {_trend_color(intra_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';")

    # Kich ban
    window.ai_lbl_scenario_a.setText(result.get('scenario_a', '--'))
    window.ai_lbl_scenario_b.setText(result.get('scenario_b', '--'))

    # HTF Bias
    htf = result.get('_htf_bias', '--')
    htf_map = {'BULLISH': 'T\u0103ng', 'BEARISH': 'Gi\u1ea3m', 'NEUTRAL': '\u0110i ngang'}
    htf_text = htf_map.get(htf, htf)
    window.ai_lbl_htf.setText(htf_text)
    window.ai_lbl_htf.setStyleSheet(f"color: {_trend_color(htf_text)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';")

    # Vi tri gia
    pos = result.get('_position', '--')
    pos_map = {'AT_SUPPORT': 'T\u1ea1i H\u1ed7 tr\u1ee3', 'AT_RESISTANCE': 'T\u1ea1i Kh\u00e1ng c\u1ef1', 'MIDDLE': 'Gi\u1eefa v\u00f9ng'}
    pos_text = pos_map.get(pos, pos)
    pos_color = '#3FB950' if pos == 'AT_SUPPORT' else '#F23645' if pos == 'AT_RESISTANCE' else '#8B949E'
    window.ai_lbl_position.setText(pos_text)
    window.ai_lbl_position.setStyleSheet(f"color: {pos_color}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';")

    window.ai_lbl_status.setText('')


def _run_analysis(window, sym, force=False):
    """Bat dau thread phan tich AI."""
    if not sym:
        window.ai_lbl_status.setText('Vui lòng chọn mã!')
        return
        
    window.ai_lbl_header.setText(f'{sym}  {window.current_tf_str}')
    window.ai_lbl_status.setText('\u0110ang ph\u00e2n t\u00edch...')
    window.ai_lbl_status.setStyleSheet("color: #58A6FF; font-size: 10px; font-family: 'Segoe UI';")

    if not hasattr(window, '_dead_threads'):
        window._dead_threads = []
        
    if hasattr(window, 'ai_thread') and window.ai_thread.isRunning():
        window.ai_thread.stop()
        try:
            window.ai_thread.signals.result.disconnect()
            window.ai_thread.signals.error.disconnect()
            window.ai_thread.signals.loading.disconnect()
        except Exception:
            pass
        window._dead_threads.append(window.ai_thread)
        window._dead_threads = [t for t in window._dead_threads if t.isRunning()]

    active_id = None
    if hasattr(window, 'comboAIModel') and window.comboAIModel.count() > 0:
        active_id = window.comboAIModel.currentText()

    rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)
    if rates is None or len(rates) == 0:
        window.ai_lbl_status.setText('Lỗi dữ liệu MT5!')
        return

    # Kéo thêm dữ liệu để truyền vào AI (Tránh gọi MT5 ở thread con gây sập)
    tech_data = None
    r_100 = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 100)
    if r_100 is not None and len(r_100) > 0:
        current_price = r_100[-1]['close']
        recent_highs = [r['high'] for r in r_100[-50:]]
        recent_lows = [r['low'] for r in r_100[-50:]]
        tech_data = {
            'current_price': current_price,
            'resistance': max(recent_highs) if recent_highs else current_price,
            'support': min(recent_lows) if recent_lows else current_price
        }

    d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 60)
    h4_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 60)

    window.ai_thread = AIAnalyzerThread(sym, rates, window.current_tf_str, active_id, force_refresh=force, tech_data=tech_data, d1_rates=d1_rates, h4_rates=h4_rates)
    window.ai_thread.signals.result.connect(lambda r: _update_panel_with_result(window, r), Qt.QueuedConnection)
    window.ai_thread.signals.error.connect(lambda e: _show_error(window, e), Qt.QueuedConnection)
    window.ai_thread.signals.loading.connect(lambda t: window.ai_lbl_status.setText(t), Qt.QueuedConnection)
    window.ai_thread.start()


def _show_error(window, error_text):
    window.ai_lbl_status.setText(f'L\u1ed7i: {error_text}')
    window.ai_lbl_status.setStyleSheet("color: #F23645; font-size: 10px; font-family: 'Segoe UI';")


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

    window.lbl_chart_title = QLabel('CH\u01afA CH\u1eccN M\u00c3')
    window.lbl_chart_title.setStyleSheet("color: #E5E7EB; font-size: 16px; font-weight: bold; margin-right: 20px; font-family: 'Segoe UI';")
    tf_layout.addWidget(window.lbl_chart_title)

    tfs = [
        ('M1', mt5.TIMEFRAME_M1), ('M5', mt5.TIMEFRAME_M5),
        ('M15', mt5.TIMEFRAME_M15), ('M30', mt5.TIMEFRAME_M30),
        ('H1', mt5.TIMEFRAME_H1), ('H4', mt5.TIMEFRAME_H4),
        ('D1', mt5.TIMEFRAME_D1)
    ]

    window.current_tf = mt5.TIMEFRAME_H1
    window.current_tf_str = 'H1'
    window.current_sym = None
    window.chart_data_list = []
    window.tf_buttons = {}

    def update_tf_styles():
        for name, btn in window.tf_buttons.items():
            if name == window.current_tf_str:
                btn.setStyleSheet('QPushButton { background-color: #1F6FEB; color: #FFFFFF; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; }')
            else:
                btn.setStyleSheet('QPushButton { background-color: transparent; color: #8B949E; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; } QPushButton:hover { background-color: #21262D; color: #C9D1D9; }')

    for (name, tf_val) in tfs:
        btn = QPushButton(name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, v=tf_val, n=name: change_timeframe(v, n))
        window.tf_buttons[name] = btn
        tf_layout.addWidget(btn)

    update_tf_styles()
    tf_layout.addStretch()
    chart_layout.addWidget(tf_widget)

    if hasattr(window, 'chartSplitter'):
        window.chartSplitter.setSizes([900, 280])

    window.time_axis = TimeAxisItem(orientation='bottom')
    window.plot_widget = pg.PlotWidget(background='#0D1117', axisItems={'bottom': window.time_axis})
    window.plot_widget.setMouseEnabled(x=True, y=False)
    window.plot_widget.showGrid(x=True, y=True, alpha=0.08)
    window.plot_widget.getAxis('left').setPen(pg.mkPen(color='#30363D'))
    window.plot_widget.getAxis('bottom').setPen(pg.mkPen(color='#30363D'))
    window.plot_widget.getAxis('left').setTextPen(pg.mkPen(color='#8B949E'))
    window.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(color='#8B949E'))
    chart_layout.addWidget(window.plot_widget)

    # Add Crosshair lines
    window.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#8B949E', style=QtCore.Qt.DashLine))
    window.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#8B949E', style=QtCore.Qt.DashLine))
    window.plot_widget.addItem(window.vLine, ignoreBounds=True)
    window.plot_widget.addItem(window.hLine, ignoreBounds=True)
    
    # Crosshair text label
    window.crosshair_label = pg.TextItem(color='#E5E7EB', anchor=(0, 1), fill=pg.mkBrush(0, 0, 0, 150))
    window.crosshair_label.setZValue(10) # ensure it's on top
    window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)
    
    # Current price line
    window.current_price_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#3FB950', style=QtCore.Qt.DotLine))
    window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)
    
    def mouseMoved(evt):
        pos = evt
        if window.plot_widget.sceneBoundingRect().contains(pos):
            mousePoint = window.plot_widget.plotItem.vb.mapSceneToView(pos)
            x = mousePoint.x()
            y = mousePoint.y()
            
            if hasattr(window, 'chart_data_list') and window.chart_data_list:
                idx = int(round(x))
                if 0 <= idx < len(window.chart_data_list):
                    t_val = window.time_axis.timestamps[idx]
                    dt_str = datetime.fromtimestamp(t_val).strftime('%d/%m %H:%M')
                    data = window.chart_data_list[idx]
                    o, c, l, h = data[1], data[2], data[3], data[4]
                    
                    fmt = ".5f" if y < 10 else ".3f"
                    window.crosshair_label.setText(f"{dt_str} | O:{o:{fmt}} H:{h:{fmt}} L:{l:{fmt}} C:{c:{fmt}}\nGiá: {y:{fmt}}")
                    
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
        if not hasattr(window, 'current_sym') or sym != window.current_sym:
            return
        
        window.current_price_line.setPos(bid)
        
        rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 1)
        if rates is not None and len(rates) > 0 and hasattr(window, 'chart_data_list') and window.chart_data_list:
            r = rates[0]
            last_idx = window.chart_data_list[-1][0]
            last_time = window.time_axis.timestamps[-1]
            
            changed = False
            if r['time'] == last_time:
                window.chart_data_list[-1] = (last_idx, r['open'], r['close'], r['low'], r['high'])
                changed = True
            elif r['time'] > last_time:
                new_idx = last_idx + 1
                window.chart_data_list.append((new_idx, r['open'], r['close'], r['low'], r['high']))
                window.time_axis.timestamps.append(r['time'])
                changed = True
                
            if changed and hasattr(window, 'candlesticks'):
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
            visible_data = window.chart_data_list[x_min:x_max+1]
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
        if mt5.terminal_info() is None:
            return
        mt5.symbol_select(sym, True)

        rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)
        if rates is None or len(rates) == 0:
            return

        window.chart_data_list = []
        timestamps = []
        for i in range(len(rates)):
            r = rates[i]
            window.chart_data_list.append((i, r['open'], r['close'], r['low'], r['high']))
            timestamps.append(r['time'])

        window.time_axis.update_timestamps(timestamps)
        window.plot_widget.clear()
        window.lbl_chart_title.setText(f'{sym}  |  {window.current_tf_str}')

        window.candlesticks = CandlestickItem(window.chart_data_list)
        window.plot_widget.addItem(window.candlesticks)
        
        # Thêm lại crosshair và live price line do hàm clear() đã xóa mất
        if hasattr(window, 'vLine'): window.plot_widget.addItem(window.vLine, ignoreBounds=True)
        if hasattr(window, 'hLine'): window.plot_widget.addItem(window.hLine, ignoreBounds=True)
        if hasattr(window, 'crosshair_label'): window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)
        if hasattr(window, 'current_price_line'): window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

        total_candles = len(window.chart_data_list)
        window.plot_widget.setLimits(xMin=-20, xMax=total_candles+20)
        view_bars = min(120, total_candles)
        window.plot_widget.setXRange(total_candles - view_bars, total_candles + 5)
        update_y_range()

        window.current_sym = sym
        _run_analysis(window, sym)

    def on_watchlist_click(item, column):
        sym = item.text(0)
        if sym.startswith('v '):
            return
        window.current_sym = sym
        draw_and_analyze(sym)

    window.treeWatchlist.itemDoubleClicked.connect(on_watchlist_click)
