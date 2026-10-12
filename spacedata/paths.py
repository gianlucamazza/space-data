"""Repository paths. The package lives one level below the repo root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
CATALOG = DATA / "catalog"
