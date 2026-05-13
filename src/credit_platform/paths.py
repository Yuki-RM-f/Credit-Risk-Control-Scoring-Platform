from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "data" / "model_artifacts" / "home-credit-gpu-full"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "runtime" / "credit_platform.sqlite3"
SOURCE_ARTIFACT_DIR = (
    PROJECT_ROOT.parent
    / "kaggle-Home-Credit-Default-Risk"
    / "artifacts"
    / "home-credit-gpu-full"
)
HOME_CREDIT_SOURCE_DIR = PROJECT_ROOT.parent / "kaggle-Home-Credit-Default-Risk" / "src"
