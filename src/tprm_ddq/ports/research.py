"""AdverseMediaPort: severity-ordered adverse-media findings (cdd-sow-research's research shape,
slice 4).

``search(subject_name)`` returns severity-ordered findings carrying synthesised MEDIA citations,
exactly as cdd-sow-research's ``adverse_media_service`` does. The GCP adapter isolates
``google_search`` grounding in its own sub-agent so web egress stays in one place (lazy import);
``local`` returns a fictional fixture corpus; ``onprem`` fails fast. Financial figures are extracted
through the extraction port (a financial statement is just another document), not here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.tprm_models import MediaFinding


@runtime_checkable
class AdverseMediaPort(Protocol):
    def search(self, subject_name: str) -> tuple[MediaFinding, ...]:
        """Return severity-ordered adverse-media findings for ``subject_name``."""
        ...
