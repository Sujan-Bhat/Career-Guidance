"""Shared test setup: make the data/ modules importable from ml tests."""
import pathlib
import sys

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
for sub in ("simulator", "seeds"):
    path = str(DATA_DIR / sub)
    if path not in sys.path:
        sys.path.insert(0, path)
