"""Backend adapter contract for dynamic analysis execution."""

from __future__ import annotations

from typing import Any, Protocol


class DynamicAnalysisBackend(Protocol):
    """Protocol for pluggable dynamic analysis backends."""

    backend_name: str

    def run(self, task_id: str, retry_context: object | None = None) -> dict[str, Any]:
        """Execute dynamic analysis and return the normalized result."""

