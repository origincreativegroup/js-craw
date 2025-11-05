"""Company data sources used by the company update pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from app.services.company_update_pipeline import CompanyRecord

logger = logging.getLogger(__name__)


class CompanyDataSource:
    """Interface for sources that provide company records."""

    async def fetch(self) -> Iterable[CompanyRecord]:  # pragma: no cover - interface method
        raise NotImplementedError


@dataclass
class SeedFileCompanySource(CompanyDataSource):
    """Load company seeds from a JSON file for ingestion."""

    seed_file: Path
    source_name: str = "seed_file"

    async def fetch(self) -> Iterable[CompanyRecord]:
        if not self.seed_file.exists():
            logger.warning("Seed file %s missing", self.seed_file)
            return []

        try:
            with self.seed_file.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            logger.error("Unable to parse %s: %s", self.seed_file, exc)
            return []

        records: List[CompanyRecord] = []
        for item in payload:
            try:
                record = CompanyRecord(
                    name=item["name"].strip(),
                    career_page_url=item["career_page_url"].strip(),
                    source=item.get("source") or self.source_name,
                    priority=int(item.get("priority", 0)),
                    has_crawl_results=bool(item.get("has_crawl_results", False)),
                    metadata={
                        key: value
                        for key, value in item.items()
                        if key
                        not in {
                            "name",
                            "career_page_url",
                            "source",
                            "priority",
                            "has_crawl_results",
                        }
                    },
                )
                records.append(record)
            except KeyError as exc:
                logger.warning("Skipping malformed seed entry %s: missing %s", item, exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to load seed entry %s: %s", item, exc)

        return records


@dataclass
class MemoryCompanySource(CompanyDataSource):
    """Simple in-memory list source, primarily for tests."""

    records: Iterable[CompanyRecord]
    source_name: Optional[str] = None

    async def fetch(self) -> Iterable[CompanyRecord]:
        records = list(self.records)
        if self.source_name:
            for record in records:
                record.source = self.source_name
        return records

