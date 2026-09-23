"""Default locations for the source checkout, independent of the working directory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "project_docs" / "data"
OUTPUT_DIR = PROJECT_ROOT / "out"
CONFIG_PATH = Path(__file__).with_name("config.yaml")
