import os, json
import MetaTrader5 as mt5
from PySide6.QtWidgets import QLabel, QComboBox

class SettingsManager:
    def __init__(self, window):
        self.window = window
        self.setup_comboboxes()
        
    def setup_comboboxes(self):
        # 1. AI Model
        if hasattr(self.window, 'comboAIModel'):
            self.window.comboAIModel.clear()
            # Chi de lai dung cac model ma he thong dang dung
            self.window.comboAIModel.addItems(["qwen2.5", "gemini-3.5-flash"])
        
        # 2. Bias
        if hasattr(self.window, 'comboBias'):
            self.window.comboBias.clear()
            self.window.comboBias.addItem("Tự động", "AUTO")
            self.window.comboBias.addItem("Chỉ Mua", "LONG_ONLY")
            self.window.comboBias.addItem("Chỉ Bán", "SHORT_ONLY")

        # 3. Timeframe
        if hasattr(self.window, 'comboTimeframe'):
            self.window.comboTimeframe.clear()
            self.window.comboTimeframe.addItem("M1", mt5.TIMEFRAME_M1)
            self.window.comboTimeframe.addItem("M5", mt5.TIMEFRAME_M5)
            self.window.comboTimeframe.addItem("M15", mt5.TIMEFRAME_M15)
            self.window.comboTimeframe.addItem("M30", mt5.TIMEFRAME_M30)
            self.window.comboTimeframe.addItem("H1", mt5.TIMEFRAME_H1)
            self.window.comboTimeframe.addItem("H4", mt5.TIMEFRAME_H4)
            self.window.comboTimeframe.addItem("D1", mt5.TIMEFRAME_D1)
            self.window.comboTimeframe.setCurrentIndex(2)

        # 4. Strategy
        if hasattr(self.window, 'comboStrategy'):
            self.window.comboStrategy.clear()
            self.window.comboStrategy.addItem("ICT Zones Pro (V1)", "ICT")
            self.window.comboStrategy.addItem("SMC Liquidity (Sắp ra mắt)", "SMC")
            self.window.comboStrategy.addItem("AI Sentiment (Sắp ra mắt)", "AI")
