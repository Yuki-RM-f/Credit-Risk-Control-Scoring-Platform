from __future__ import annotations

import app


def test_load_runtime_recreates_repository_objects(monkeypatch) -> None:
    artifacts = object()
    created_repositories = []

    def fake_initialize_platform(*, seed_demo: bool):
        repo = object()
        service = object()
        created_repositories.append(repo)
        assert seed_demo is True
        return artifacts, repo, service

    monkeypatch.setattr(app, "initialize_platform", fake_initialize_platform, raising=False)
    monkeypatch.setattr(app, "load_platform_artifacts_resource", lambda: artifacts, raising=False)

    def fake_create_platform_runtime(loaded_artifacts, *, seed_demo: bool):
        repo = object()
        service = object()
        created_repositories.append(repo)
        assert loaded_artifacts is artifacts
        assert seed_demo is True
        return repo, service

    monkeypatch.setattr(app, "create_platform_runtime", fake_create_platform_runtime, raising=False)

    first_artifacts, first_repo, _ = app.load_runtime()
    second_artifacts, second_repo, _ = app.load_runtime()

    assert first_artifacts is artifacts
    assert second_artifacts is artifacts
    assert first_repo is created_repositories[0]
    assert second_repo is created_repositories[1]
    assert first_repo is not second_repo
