"""Export only after the canonical chronological validation pipeline succeeds.
Usage: python research/export_trained_wyckoff_model.py --data completed_M15.csv
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.walk_forward_pipeline import main

if __name__=='__main__':
    argv=sys.argv[1:]
    if '--export-model' not in argv:
        argv += ['--export-model',str(ROOT/'storage/models/builtin_wyckoff_meta.lgb')]
    main(argv)
