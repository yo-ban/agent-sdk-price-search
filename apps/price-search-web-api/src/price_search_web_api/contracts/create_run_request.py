"""Create run request contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateRunRequest:
    """Input required to start a new launcher-backed run."""

    product_name: str
    market: str
    currency: str
    max_offers: int

