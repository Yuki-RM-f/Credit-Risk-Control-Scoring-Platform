from __future__ import annotations

import shutil
from pathlib import Path

from .artifact_loader import PlatformArtifacts, load_artifacts
from .database import CreditRepository
from .paths import DEFAULT_ARTIFACT_DIR, DEFAULT_DB_PATH, SOURCE_ARTIFACT_DIR
from .scoring_service import ScoringService


def ensure_artifact_bundle(
    target_dir: Path = DEFAULT_ARTIFACT_DIR,
    source_dir: Path = SOURCE_ARTIFACT_DIR,
) -> Path:
    if target_dir.exists():
        return target_dir
    if not source_dir.exists():
        raise FileNotFoundError(
            f"Model artifacts not found. Expected copied bundle at {target_dir} or source bundle at {source_dir}."
        )
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
    return target_dir


def initialize_platform(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    seed_demo: bool = True,
) -> tuple[PlatformArtifacts, CreditRepository, ScoringService]:
    artifact_path = ensure_artifact_bundle(artifact_dir)
    artifacts = load_artifacts(artifact_path)
    repo = CreditRepository(db_path)
    repo.initialize()
    service = ScoringService(artifacts, strategy_version=repo.get_active_strategy()["strategy_version"])
    if seed_demo and repo.is_empty():
        seed_demo_applications(repo, service)
    return artifacts, repo, service


def seed_demo_applications(repo: CreditRepository, service: ScoringService) -> None:
    for sample_key in service.list_samples():
        result = service.score_sample(sample_key)
        repo.create_application(result.profile, result)
