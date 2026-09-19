"""Provider registry. A real deployment sets WEALTH_LAB_PROVIDER to a
registered name (after implementing and registering it - see
providers/README.md); every environment defaults to "mock", which is
honest about returning nothing rather than silently the wrong thing.
"""

from __future__ import annotations

import os

from wealth_lab.providers.base import DataProvider, Fundamentals, NewsItem
from wealth_lab.providers.mock import MockProvider

_REGISTRY: dict[str, type[DataProvider]] = {
    "mock": MockProvider,
}


def register_provider(name: str, provider_cls: type[DataProvider]) -> None:
    """Call this from your own provider module before get_provider() runs
    (e.g. at app startup) to make WEALTH_LAB_PROVIDER=<name> select it."""
    _REGISTRY[name] = provider_cls


def get_provider() -> DataProvider:
    name = os.environ.get("WEALTH_LAB_PROVIDER", "mock")
    if name == "finnhub" and "finnhub" not in _REGISTRY:
        # imported lazily so the default (mock) path never needs `requests`
        # installed - only a deployment that opts into WEALTH_LAB_PROVIDER=finnhub
        # needs requirements-live.txt
        from wealth_lab.providers.finnhub import FinnhubProvider
        register_provider("finnhub", FinnhubProvider)
    if name not in _REGISTRY:
        raise ValueError(
            f"unknown provider {name!r} (WEALTH_LAB_PROVIDER env var) - "
            f"registered: {sorted(_REGISTRY)}. See providers/README.md."
        )
    return _REGISTRY[name]()


__all__ = ["DataProvider", "Fundamentals", "NewsItem", "MockProvider", "get_provider", "register_provider"]
