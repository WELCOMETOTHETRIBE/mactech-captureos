"""Safe archive (ZIP) expansion.

SAM resource packages are frequently ZIPs of the real documents. Expanding
untrusted archives is dangerous (zip bombs, path traversal, nested-archive
explosions), so every limit below is enforced and any breach raises
``ArchiveError`` rather than proceeding. Embedded macros/executables are never
run — we only read bytes.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

# Bomb/DoS protection.
MAX_MEMBERS = 200
MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024  # 200 MB expanded, across all members
MAX_MEMBER_UNCOMPRESSED = 60 * 1024 * 1024  # 60 MB per member
MAX_COMPRESSION_RATIO = 200  # a member expanding >200x its stored size is a bomb
MAX_ARCHIVE_DEPTH = 2  # zip-in-zip allowed once; no deeper

# Extensions we refuse to surface out of an archive (never executed, but not
# worth parsing/storing either).
_BLOCKED_SUFFIXES = (
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".msi",
    ".js",
    ".vbs",
    ".ps1",
    ".sh",
    ".jar",
)


class ArchiveError(Exception):
    """Raised when an archive violates a safety limit."""


@dataclass(frozen=True)
class ExtractedFile:
    """One file surfaced from an archive."""

    filename: str  # basename only (path components stripped)
    data: bytes
    archived_from: str  # the archive path this came out of


def is_zip(blob: bytes) -> bool:
    return blob[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _safe_basename(name: str) -> str:
    # Defeat path traversal: keep only the final component, drop separators.
    cleaned = name.replace("\\", "/").split("/")[-1].strip()
    return cleaned or "unnamed"


def expand_archive(
    blob: bytes,
    *,
    source_name: str,
    _depth: int = 1,
) -> list[ExtractedFile]:
    """Expand a ZIP into a flat list of member files, recursing into nested
    ZIPs up to ``MAX_ARCHIVE_DEPTH``. Raises ``ArchiveError`` on any limit
    breach so the caller can mark the document ``failed_permanent`` rather than
    ingest a bomb."""
    if _depth > MAX_ARCHIVE_DEPTH:
        raise ArchiveError(f"archive nesting exceeds depth {MAX_ARCHIVE_DEPTH}: {source_name}")

    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"bad zip {source_name}: {exc}") from exc

    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_MEMBERS:
        raise ArchiveError(f"archive has {len(infos)} members (> {MAX_MEMBERS}): {source_name}")

    out: list[ExtractedFile] = []
    total = 0
    with zf:
        for info in infos:
            size = info.file_size
            if size > MAX_MEMBER_UNCOMPRESSED:
                raise ArchiveError(
                    f"member {info.filename!r} is {size} bytes (> {MAX_MEMBER_UNCOMPRESSED})"
                )
            if info.compress_size > 0 and size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ArchiveError(
                    f"member {info.filename!r} compression ratio "
                    f"{size / info.compress_size:.0f}x looks like a zip bomb"
                )
            total += size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise ArchiveError(
                    f"archive expands past {MAX_TOTAL_UNCOMPRESSED} bytes: {source_name}"
                )

            base = _safe_basename(info.filename)
            if base.lower().endswith(_BLOCKED_SUFFIXES):
                continue  # skip executables/scripts entirely
            data = zf.read(info)

            if is_zip(data):
                out.extend(
                    expand_archive(
                        data,
                        source_name=f"{source_name}:{base}",
                        _depth=_depth + 1,
                    )
                )
            else:
                out.append(ExtractedFile(filename=base, data=data, archived_from=source_name))

    return out
