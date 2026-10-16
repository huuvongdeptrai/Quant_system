"""
Candlestick and TimeAxis Graphics Items for pyqtgraph
"""

import os
from datetime import datetime
import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPicture, QPainter, QColor

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

    def __init__(self, data, is_dark: bool = False):

        pg.GraphicsObject.__init__(self)

        self.data = data
        self.is_dark = is_dark

        self.generatePicture()

    def set_theme(self, is_dark: bool):
        if getattr(self, "is_dark", None) != is_dark:
            self.is_dark = is_dark
            self.generatePicture()
            self.update()

    def generatePicture(self):

        self.picture = QPicture()

        p = QPainter(self.picture)

        p.setPen(pg.mkPen("w"))

        w = 0.35

        bull_color = "#22c55e" if getattr(self, "is_dark", True) else "#15803D"
        bear_color = "#ef4444" if getattr(self, "is_dark", True) else "#B91C1C"

        for t, open, close, low, high in self.data:

            if open > close:

                p.setBrush(pg.mkBrush(bear_color))

                p.setPen(pg.mkPen(bear_color))

            else:

                p.setBrush(pg.mkBrush(bull_color))

                p.setPen(pg.mkPen(bull_color))

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


