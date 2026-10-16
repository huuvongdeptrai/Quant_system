# -*- coding: utf-8 -*-
"""
Asset Registry & Dynamic Context Dispatcher.
Automatically identifies the asset class from any broker symbol and dispatches the corresponding context adapter.
"""
from enum import Enum
from typing import Dict
from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter
from backend.infrastructure.data_providers.adapters.precious_metals_adapter import PreciousMetalsAdapter
from backend.infrastructure.data_providers.adapters.crypto_adapter import CryptoContextAdapter


class AssetClass(Enum):
    COMMODITY_PRECIOUS = "COMMODITY_PRECIOUS"  # XAU, XAG, GOLD, SILVER
    CRYPTO = "CRYPTO"                          # BTC, ETH, SOL, XRP, DOGE
    COMMODITY_ENERGY = "COMMODITY_ENERGY"      # USOIL, UKOIL, BRENT, NGAS
    EQUITY_INDEX = "EQUITY_INDEX"              # US30, NAS100, SPX500, USTEC
    FOREX = "FOREX"                            # EURUSD, GBPUSD, USDJPY, AUDUSD


class AssetRegistry:
    """
    Quản lý phân loại tài sản và điều phối Adapter nạp ngữ cảnh phù hợp.
    """
    _adapters: Dict[AssetClass, BaseContextAdapter] = {}

    @classmethod
    def _init_adapters(cls):
        if not cls._adapters:
            metals = PreciousMetalsAdapter()
            crypto = CryptoContextAdapter()
            cls._adapters = {
                AssetClass.COMMODITY_PRECIOUS: metals,
                AssetClass.CRYPTO: crypto,
                # Forex và Hàng hóa tạm thời kế thừa macro vĩ mô từ PreciousMetals
                AssetClass.FOREX: metals,
                AssetClass.COMMODITY_ENERGY: metals,
                AssetClass.EQUITY_INDEX: metals,
            }

    @classmethod
    def identify(cls, symbol: str) -> AssetClass:
        """
        Nhận diện lớp tài sản từ tên mã giao dịch (không phân biệt hoa/thường, loại bỏ dấu gạch).
        """
        s = str(symbol).upper().replace("/", "").replace("_", "").replace(".", "").strip()

        # 1. Kim loại quý
        if any(k in s for k in ["XAU", "GOLD", "XAG", "SILVER"]):
            return AssetClass.COMMODITY_PRECIOUS

        # 2. Tiền mã hóa
        if any(k in s for k in ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "CRYPTO"]):
            return AssetClass.CRYPTO

        # 3. Năng lượng & Hàng hóa
        if any(k in s for k in ["OIL", "WTI", "BRENT", "GAS", "XNG"]):
            return AssetClass.COMMODITY_ENERGY

        # 4. Chỉ số chứng khoán
        if any(k in s for k in ["US30", "NAS100", "USTEC", "SPX500", "DJ30", "NDX"]):
            return AssetClass.EQUITY_INDEX

        # 5. Ngoại hối mặc định
        return AssetClass.FOREX

    @classmethod
    def get_adapter(cls, symbol: str) -> BaseContextAdapter:
        """
        Trả về Adapter chuyên trách cho mã giao dịch đang xét.
        """
        cls._init_adapters()
        asset_class = cls.identify(symbol)
        return cls._adapters.get(asset_class, cls._adapters[AssetClass.COMMODITY_PRECIOUS])
