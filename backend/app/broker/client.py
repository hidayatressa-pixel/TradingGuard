"""Placeholder broker client used for future integration work."""

from __future__ import annotations


class BrokerClient:
    """This module intentionally avoids credential or order-execution logic."""

    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> bool:
        """A no-op placeholder for future broker integration."""
        self.connected = False
        return False
