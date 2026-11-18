"""Shared exceptions."""

from __future__ import annotations


class TooShortError(RuntimeError):
    """Raised when a recording is shorter than the configured threshold.

    This is a skip, not a processing failure: the watcher files it under
    ``skipped/`` instead of ``quarantine/``.
    """

    def __init__(self, seconds: float, minimum: int):
        self.seconds = seconds
        self.minimum = minimum
        super().__init__(
            f"recording is shorter than {minimum}s (duration {seconds:.0f}s)"
        )
