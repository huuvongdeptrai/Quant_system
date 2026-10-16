# -*- coding: utf-8 -*-
"""
Base Context Adapter Interface for Multi-Asset Quantitative Framework.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple


class BaseContextAdapter(ABC):
    """
    Interface cơ sở cho các Adapter nạp dữ liệu và ngữ cảnh theo lớp tài sản.
    Mỗi Adapter chịu trách nhiệm thu thập, chuẩn hóa các biến số đặc thù (Driver DNA)
    và sinh ra báo cáo ngữ cảnh cho AI Engine & Decision Gate.
    """

    @abstractmethod
    def generate_context_report(self, symbol: str) -> Dict[str, Any]:
        """
        Tạo báo cáo ngữ cảnh vĩ mô / vi mô đầy đủ cho tài sản.
        Returns: dict chứa cấu trúc chuẩn hóa cho AI Engine.
        """
        pass

    @abstractmethod
    def get_macro_bias(self, symbol: str) -> str:
        """
        Trả về 'BULLISH', 'BEARISH', hoặc 'NEUTRAL' dựa trên các biến số cốt lõi.
        """
        pass

    @abstractmethod
    def build_prompt_section(self, symbol: str, context_report: Dict[str, Any]) -> str:
        """
        Sinh chuỗi văn bản định dạng chuẩn để nhúng vào Prompt của LLM.
        """
        pass

    @abstractmethod
    def evaluate_risk_rules(self, symbol: str, signal: str, context_report: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Kiểm tra các quy tắc rủi ro đặc thù của lớp tài sản (VD: Tin đỏ, Funding quá nhiệt, Token unlock).
        Returns: (is_allowed: bool, reason: str)
        """
        pass
