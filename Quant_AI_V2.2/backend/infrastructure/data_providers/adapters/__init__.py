# -*- coding: utf-8 -*-
"""
Adapters package for Multi-Asset Quantitative Context Framework.
"""
from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter
from backend.infrastructure.data_providers.adapters.precious_metals_adapter import PreciousMetalsAdapter
from backend.infrastructure.data_providers.adapters.crypto_adapter import CryptoContextAdapter

__all__ = ["BaseContextAdapter", "PreciousMetalsAdapter", "CryptoContextAdapter"]
