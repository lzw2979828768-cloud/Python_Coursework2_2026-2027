"""Per-request in-memory trace collection; never writes files."""

from typing import Any

from .models import PayloadType, TraceStep


class TraceCollector:
    def __init__(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self.enabled = enabled
        self._steps: list[TraceStep] = []
        self._ids: set[str] = set()

    def record(
        self, step_id: str, title: str, explanation: str,
        payload_type: PayloadType, payload: Any,
    ) -> None:
        """Snapshot a completed calculation; IDs are unique in this request."""
        if not self.enabled:
            return
        if step_id in self._ids:
            raise ValueError("Duplicate trace step ID")
        step = TraceStep(step_id, title, explanation, payload_type, payload)
        self._steps.append(step)
        self._ids.add(step_id)

    def steps(self) -> tuple[TraceStep, ...]:
        return tuple(self._steps)
