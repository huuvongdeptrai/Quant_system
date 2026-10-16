"""
Core Micro-services Module
Contains 5 core business layers and strategy plugins.
"""

import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BE_DIR = os.path.join(ROOT_DIR, "backend")
if BE_DIR not in sys.path:
    sys.path.insert(0, BE_DIR)
