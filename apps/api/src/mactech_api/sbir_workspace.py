"""On-disk workspace for SBIR Submission Engine outputs.

The engine writes the generated submission package (markdown volumes,
DSIP cheat sheet, evidence pack, etc.) to a per-topic directory under the
repo's `docs/` tree, matching the prompt's stated default of
`docs/sbir-{TOPIC_NUMBER}/submission/`.

Path resolution:
  * If env `SBIR_SUBMISSIONS_ROOT` is set, use that as the parent.
  * Otherwise walk up from this file until we find `pnpm-workspace.yaml`
    (the monorepo marker) and use `<repo>/docs`.

Every write goes through `write_artifact()` which enforces the per-
submission sandbox — relative paths only, no `..`, no absolute paths.
Reads use `resolve_artifact_path()` with the same guard so the file
download endpoint can't be coerced into serving arbitrary files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_REPO_MARKER = "pnpm-workspace.yaml"
_TOPIC_RE = re.compile(r"[^a-z0-9._-]+")


def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / _REPO_MARKER).exists():
            return parent
    # Fallback: assume four levels up (apps/api/src/mactech_api/ -> repo)
    return here.parents[4]


def submissions_root() -> Path:
    override = os.environ.get("SBIR_SUBMISSIONS_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _resolve_repo_root() / "docs"


def slugify_topic(topic_number: str) -> str:
    """Make a topic identifier safe for a directory name.

    DLA26BZ02-NV007 -> dla26bz02-nv007. Strips anything not alphanumeric,
    dot, dash, or underscore. Empty result is rejected by caller.
    """
    return _TOPIC_RE.sub("-", topic_number.strip().lower()).strip("-._")


@dataclass(frozen=True)
class SBIRWorkspace:
    """Resolved on-disk location for one submission's artifacts."""

    topic_number: str
    root: Path  # the per-submission directory (created lazily)

    @classmethod
    def for_topic(cls, topic_number: str) -> SBIRWorkspace:
        slug = slugify_topic(topic_number)
        if not slug:
            raise ValueError(f"invalid topic_number: {topic_number!r}")
        return cls(
            topic_number=topic_number,
            root=submissions_root() / f"sbir-{slug}" / "submission",
        )

    @property
    def relative_to_repo(self) -> str:
        """`docs/sbir-…/submission` — what the DB persists."""
        try:
            return str(self.root.relative_to(_resolve_repo_root()))
        except ValueError:
            return str(self.root)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relpath: str) -> Path:
        """Resolve a relative artifact path inside this workspace.

        Rejects absolute paths and traversal segments. Raises ValueError
        on rejection (callers translate to 404). The path itself does
        not have to exist.
        """
        cleaned = (relpath or "").strip()
        if not cleaned:
            raise ValueError("empty path")
        candidate = Path(cleaned)
        # Reject absolute paths and any traversal segment up front. Leading
        # slashes are NOT silently stripped — that would let `/etc/passwd`
        # masquerade as a relative `etc/passwd` inside the workspace.
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"unsafe path: {relpath!r}")
        target = (self.root / candidate).resolve()
        root_resolved = self.root.resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(f"path escapes workspace: {relpath!r}") from exc
        return target

    def write_artifact(self, relpath: str, content: str | bytes) -> Path:
        target = self.resolve(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
        return target

    def list_files(self) -> list[tuple[str, int]]:
        if not self.root.exists():
            return []
        out: list[tuple[str, int]] = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(self.root).as_posix()
                out.append((rel, path.stat().st_size))
        return out
