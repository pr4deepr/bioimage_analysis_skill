import pathlib
import sys

# Make references/ importable as a flat module path (spatial_clustering.py).
REFERENCES = pathlib.Path(__file__).resolve().parent.parent / "references"
sys.path.insert(0, str(REFERENCES))
