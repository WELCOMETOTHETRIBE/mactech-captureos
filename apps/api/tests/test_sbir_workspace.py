"""Path-traversal + slug rules for the SBIR workspace.

This is the only security boundary between an authenticated user and
arbitrary file reads on the API host, so the unit tests carry the
load even though there is no DB harness for the full route tests yet.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from mactech_api.sbir_workspace import SBIRWorkspace, slugify_topic, submissions_root


def test_slugify_topic_canonicalizes() -> None:
    assert slugify_topic("DLA26BZ02-NV007") == "dla26bz02-nv007"
    assert slugify_topic("  AF26-D001  ") == "af26-d001"
    assert slugify_topic("Topic With Spaces!") == "topic-with-spaces"


def test_slugify_topic_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        SBIRWorkspace.for_topic("")
    with pytest.raises(ValueError):
        SBIRWorkspace.for_topic("!!!")


def test_resolve_rejects_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SBIR_SUBMISSIONS_ROOT", str(tmp_path))
    ws = SBIRWorkspace.for_topic("DLA26BZ02-NV999")
    ws.ensure()

    with pytest.raises(ValueError):
        ws.resolve("../../etc/passwd")
    with pytest.raises(ValueError):
        ws.resolve("/etc/passwd")
    with pytest.raises(ValueError):
        ws.resolve("nested/../../../etc/passwd")
    with pytest.raises(ValueError):
        ws.resolve("")


def test_resolve_allows_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SBIR_SUBMISSIONS_ROOT", str(tmp_path))
    ws = SBIRWorkspace.for_topic("DLA26BZ02-NV999")
    ws.ensure()
    target = ws.resolve("volume-5-supporting/01-pi-cv.md")
    assert target.parent.name == "volume-5-supporting"
    assert str(target).startswith(str(ws.root.resolve()))


def test_write_and_list_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SBIR_SUBMISSIONS_ROOT", str(tmp_path))
    ws = SBIRWorkspace.for_topic("DLA26BZ02-NV999")
    ws.ensure()

    ws.write_artifact("topic-extract.md", "Hello\n")
    ws.write_artifact("volume-5-supporting/01-pi-cv.md", "PI CV body\n")

    files = dict(ws.list_files())
    assert "topic-extract.md" in files
    assert "volume-5-supporting/01-pi-cv.md" in files
    assert files["topic-extract.md"] > 0


def test_submissions_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SBIR_SUBMISSIONS_ROOT", str(tmp_path))
    assert submissions_root() == tmp_path.resolve()


def test_submissions_root_default_uses_repo_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SBIR_SUBMISSIONS_ROOT", raising=False)
    root = submissions_root()
    # Either the captureOS repo's docs/ (when running inside the repo) or a
    # plausible parents-up resolution. Don't pin to either — assert the
    # path component is `docs`.
    assert root.name == "docs"
    # Sanity: avoid accidentally pointing at /docs at the filesystem root.
    assert str(root) != "/docs"
    _ = os.environ  # touch to keep import meaningful
