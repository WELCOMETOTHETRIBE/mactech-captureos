"""Procurement-document toolkit (Slice 2).

Pure, dependency-light helpers for acquiring and parsing the full procurement
package: safe archive expansion, multi-format text extraction, document
classification, section/page provenance, and an object store for the original
binaries. The generalized ``attachment_fetcher`` worker composes these; none of
them touch the database or network, so they are unit-testable in isolation.
"""

from mactech_workers.documents.archive import ArchiveError, ExtractedFile, expand_archive
from mactech_workers.documents.classify import classify_document
from mactech_workers.documents.extract import ExtractedDoc, detect_format, extract_text
from mactech_workers.documents.sections import Section, build_sections
from mactech_workers.documents.store import (
    DocumentStore,
    FilesystemDocumentStore,
    get_document_store,
    storage_key_for,
)

__all__ = [
    "ArchiveError",
    "DocumentStore",
    "ExtractedDoc",
    "ExtractedFile",
    "FilesystemDocumentStore",
    "Section",
    "build_sections",
    "classify_document",
    "detect_format",
    "expand_archive",
    "extract_text",
    "get_document_store",
    "storage_key_for",
]
