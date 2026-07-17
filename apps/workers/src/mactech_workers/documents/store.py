"""Object store for original procurement binaries.

The overhaul requires preserving the original binary so evidence is auditable
and documents can be re-parsed without re-fetching. The default backend is the
local filesystem (works out-of-the-box in dev and CI, keyed by ``storage_key``);
an S3/MinIO backend is a drop-in — ``docker-compose`` ships MinIO and
``.env.example`` already carries ``S3_*`` — and can be selected later by
implementing the same ``DocumentStore`` protocol behind ``get_document_store``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, runtime_checkable


def _ext_for(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    # Keep it short and safe; storage keys are content-hash based anyway.
    return suffix if 0 < len(suffix) <= 6 and suffix.isascii() else ""


def storage_key_for(opportunity_id: str, content_hash: str, filename: str) -> str:
    """Deterministic key: shard by opportunity, name by content hash. Two
    identical bytes under one opportunity collapse to one object (idempotent)."""
    return f"opportunities/{opportunity_id}/{content_hash}{_ext_for(filename)}"


@runtime_checkable
class DocumentStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class FilesystemDocumentStore:
    """Filesystem-backed store rooted at ``DOCUMENT_STORE_DIR`` (default
    ``./.captureos_documents``)."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        base = root or os.environ.get("DOCUMENT_STORE_DIR") or ".captureos_documents"
        self.root = Path(base).resolve()

    def _path(self, key: str) -> Path:
        # Prevent traversal out of root.
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError(f"unsafe storage key: {key!r}")
        return p

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


_STORE: DocumentStore | None = None


def get_document_store() -> DocumentStore:
    """Process-wide store singleton. Backend selected by ``DOCUMENT_STORE``
    (currently only ``filesystem``; ``s3`` reserved for the MinIO/S3 backend)."""
    global _STORE
    if _STORE is None:
        backend = (os.environ.get("DOCUMENT_STORE") or "filesystem").lower()
        if backend not in ("filesystem", "fs", "local"):
            # S3 backend not yet implemented; fall back rather than crash the
            # ingest pipeline. Swap in an S3DocumentStore here when wired.
            pass
        _STORE = FilesystemDocumentStore()
    return _STORE
