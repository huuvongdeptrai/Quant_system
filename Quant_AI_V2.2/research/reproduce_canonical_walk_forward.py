"""Canonical entry point: independent capital replay, validation-only tuning.
The former cached-PnL aggregation is retained only in the original source ZIP.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.walk_forward_pipeline import main

if __name__ == '__main__':
    main()
