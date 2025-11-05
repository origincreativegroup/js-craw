"""Pipeline used to assemble and verify the companies catalog."""

from __future__ import annotations

import asyncio
import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Protocol, Sequence

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CompanyRecord:
    """Structured representation for a single company."""

    name: str
    career_page_url: str
    source: str
    priority: int = 0
    has_crawl_results: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_csv_row(self) -> dict[str, Any]:
        """Map the record to a CSV row."""

        return {
            "Company Name": self.name,
            "Career Page URL": self.career_page_url,
            "Source": self.source,
            "Priority": str(self.priority),
            "Notes": self.metadata.get("notes", ""),
        }


class CompanyHeuristic(Protocol):
    """Protocol for asynchronous company keep/discard heuristics."""

    async def evaluate(self, record: CompanyRecord) -> bool:  # pragma: no cover - interface
        ...


class AICompanyHeuristic:
    """Heuristic that defers to an AI endpoint and falls back to rule checks."""

    def __init__(self, http_client_factory=None):
        self._http_client_factory = http_client_factory

    async def evaluate(self, record: CompanyRecord) -> bool:
        ai_enabled = getattr(settings, "WEB_SEARCH_ENABLED", False)
        if not ai_enabled:
            return self._fallback(record)

        if self._http_client_factory is None:
            return self._fallback(record)

        try:  # pragma: no cover - network interaction
            async with self._http_client_factory() as client:  # type: ignore[attr-defined]
                prompt = (
                    "Determine if the following company is relevant for technology job seekers. "
                    "Answer with 'keep' or 'discard'.\n"
                    f"Company: {record.name}\n"
                    f"Careers URL: {record.career_page_url}\n"
                    f"Source: {record.source}\n"
                    f"Metadata: {record.metadata}\n"
                )
                response = await client.post(
                    f"{settings.OLLAMA_HOST}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                    timeout=30,
                )
            if response.status_code == 200:
                decision = response.json().get("response", "").lower()
                if "keep" in decision and "discard" not in decision:
                    return True
                if "discard" in decision and "keep" not in decision:
                    return False
        except Exception as exc:
            logger.debug("AI heuristic failed, using fallback: %s", exc)

        return self._fallback(record)

    def _fallback(self, record: CompanyRecord) -> bool:
        priority_threshold = 40
        if record.priority >= priority_threshold:
            return True

        industry = (record.metadata.get("industry") or "").lower()
        if any(keyword in industry for keyword in ("software", "technology", "ai")):
            return True

        return False


class CompanyFilteringPipeline:
    """Pipeline that prioritises records and enforces a hard cap."""

    def __init__(self, cap: int = 1500):
        self.cap = cap

    def apply(self, records: Sequence[CompanyRecord]) -> List[CompanyRecord]:
        logger.info("Applying company filtering pipeline to %s records", len(records))

        ordered = sorted(
            records,
            key=lambda record: (
                record.has_crawl_results,
                record.priority,
                record.name.lower(),
            ),
            reverse=True,
        )

        if len(ordered) > self.cap:
            logger.warning(
                "Company list exceeds cap (%s > %s). Truncating results.",
                len(ordered),
                self.cap,
            )

        trimmed = ordered[: self.cap]
        logger.info("Filtered down to %s companies", len(trimmed))
        return trimmed


class CompanyVerifier:
    """Verification stage that keeps companies with crawl data or AI approval."""

    def __init__(self, heuristic: Optional[CompanyHeuristic] = None):
        self.heuristic = heuristic or AICompanyHeuristic()

    async def verify_many(self, records: Iterable[CompanyRecord]) -> List[CompanyRecord]:
        verified: List[CompanyRecord] = []
        for record in records:
            if record.has_crawl_results:
                logger.debug("%s retained (existing crawl results)", record.name)
                verified.append(record)
                continue

            keep = await self.heuristic.evaluate(record)
            if keep:
                logger.debug("%s retained by heuristic", record.name)
                verified.append(record)
            else:
                logger.debug("%s removed by heuristic", record.name)

        logger.info("Verification completed. %s companies retained.", len(verified))
        return verified


class CompanyCollector:
    """Collect company records from configured sources."""

    def __init__(self, sources: Sequence):
        self.sources = list(sources)

    async def collect(self) -> List[CompanyRecord]:
        records: List[CompanyRecord] = []

        for source in self.sources:
            logger.info("Collecting companies from %s", source)
            result = await source.fetch()
            records.extend(result)

        logger.info("Collected %s company records", len(records))
        return records


async def run_company_update(
    collector: CompanyCollector,
    verifier: CompanyVerifier,
    output_path: Path,
    cap: int = 1500,
) -> List[CompanyRecord]:
    """Orchestrate the company update pipeline and write a CSV file."""

    records = await collector.collect()

    filtering = CompanyFilteringPipeline(cap=cap)
    filtered = filtering.apply(records)

    verified = await verifier.verify_many(filtered)

    write_companies_csv(verified, output_path)

    return verified


def write_companies_csv(records: Iterable[CompanyRecord], output_path: Path) -> None:
    fieldnames = ["Company Name", "Career Page URL", "Source", "Priority", "Notes"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records_list = list(records)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records_list:
            writer.writerow(record.as_csv_row())

    logger.info("Wrote %s companies to %s", len(records_list), output_path)


def run_sync(coro):
    """Run an async coroutine in a synchronous context."""

    return asyncio.run(coro)

