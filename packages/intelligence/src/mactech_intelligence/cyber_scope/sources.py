"""Text source adapters for cyber scope analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SourceType = Literal[
    "SAM_INGEST",
    "SAM_SEARCH",
    "PASTED_TEXT",
    "UPLOAD",
    "FPDS_SEARCH",
    "OTHER",
]


@dataclass(frozen=True)
class CyberScopeTextSource:
    source_type: SourceType
    title: str | None
    description_text: str | None
    attachment_text: str | None
    metadata: dict[str, Any]
    scan_pass: Literal["description_only", "with_attachments"] = "description_only"

    @property
    def combined_text(self) -> str:
        parts = [self.title, self.description_text, self.attachment_text]
        return "\n\n".join(p for p in parts if p)

    @classmethod
    def from_opportunity(
        cls,
        *,
        title: str | None,
        description_text: str | None,
        attachment_text: str | None,
        opportunity_id: str | None = None,
        agency: str | None = None,
        solicitation_number: str | None = None,
        source_url: str | None = None,
    ) -> CyberScopeTextSource:
        has_attachments = bool(attachment_text and attachment_text.strip())
        return cls(
            source_type="SAM_INGEST",
            title=title,
            description_text=description_text,
            attachment_text=attachment_text,
            scan_pass="with_attachments" if has_attachments else "description_only",
            metadata={
                "opportunity_id": opportunity_id,
                "agency": agency,
                "solicitation_number": solicitation_number,
                "source_url": source_url,
            },
        )

    @classmethod
    def from_paste(cls, text: str, metadata: dict[str, Any] | None = None) -> CyberScopeTextSource:
        return cls(
            source_type="PASTED_TEXT",
            title=metadata.get("title") if metadata else None,
            description_text=text,
            attachment_text=None,
            metadata=metadata or {},
            scan_pass="description_only",
        )
