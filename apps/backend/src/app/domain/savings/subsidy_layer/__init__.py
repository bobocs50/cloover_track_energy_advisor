"""Subsidy layer (F26) — DB-driven, official-sourced, cited federal subsidies.

The catalog is the single source of truth the financing engine reads. A separate
crawler only *proposes* updates (see crawler.py); it never overwrites the live rate.
"""
from app.domain.savings.subsidy_layer.catalog import (
    Subsidy,
    SubsidyContext,
    components_for_intake,
    resolve_subsidies,
)
from app.domain.savings.subsidy_layer.crawler import CrawlResult, refresh_federal

__all__ = [
    "Subsidy",
    "SubsidyContext",
    "CrawlResult",
    "components_for_intake",
    "refresh_federal",
    "resolve_subsidies",
]
