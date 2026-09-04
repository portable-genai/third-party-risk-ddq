"""DocumentExtractionPort: parse a vendor evidence document (credit-memo-drafting's extraction
shape).

``extract(document)`` returns the document's full text plus deterministically parsed structure
(tested control observations, free-text DDQ answers, financial figures). The primary adapter is
GCP Document AI (lazy import); ``local`` reads a fictional fixture corpus (a SOC 2 Type II report
with exceptions, an ISO 27001 certificate plus SoA, a SIG/CAIQ-style DDQ); ``onprem`` fails fast.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.tprm_models import DocumentRef, ExtractedDocument


@runtime_checkable
class DocumentExtractionPort(Protocol):
    def extract(self, document: DocumentRef) -> ExtractedDocument:
        """Extract structured fields plus full text from one evidence document."""
        ...
