from pathlib import Path

import pytest

from app.services.company_sources import MemoryCompanySource
from app.services.company_update_pipeline import (
    CompanyCollector,
    CompanyRecord,
    CompanyVerifier,
    CompanyFilteringPipeline,
    write_companies_csv,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_filtering_enforces_cap_and_priority(tmp_path: Path):
    records = [
        CompanyRecord(
            name=f"Company {i:04d}",
            career_page_url=f"https://example{i}.com/careers",
            source="test",
            priority=i % 100,
            has_crawl_results=(i % 10 == 0),
        )
        for i in range(2000)
    ]

    collector = CompanyCollector([MemoryCompanySource(records)])
    gathered = await collector.collect()

    pipeline = CompanyFilteringPipeline(cap=1500)
    filtered = pipeline.apply(gathered)

    assert len(filtered) == 1500
    assert filtered[0].has_crawl_results is True
    assert filtered[0].priority >= filtered[-1].priority

    output_file = tmp_path / "companies.csv"
    write_companies_csv(filtered, output_file)
    assert output_file.exists()


@pytest.mark.anyio
async def test_verification_respects_ai_decision():
    keep_record = CompanyRecord(
        name="Keep Co",
        career_page_url="https://keep.example.com",
        source="test",
        priority=10,
        has_crawl_results=False,
    )
    drop_record = CompanyRecord(
        name="Drop Co",
        career_page_url="https://drop.example.com",
        source="test",
        priority=10,
        has_crawl_results=False,
    )
    already_kept = CompanyRecord(
        name="Existing",
        career_page_url="https://existing.example.com",
        source="test",
        priority=10,
        has_crawl_results=True,
    )

    class StubHeuristic:
        async def evaluate(self, record: CompanyRecord) -> bool:
            return record.name == "Keep Co"

    verifier = CompanyVerifier(heuristic=StubHeuristic())
    verified = await verifier.verify_many([keep_record, drop_record, already_kept])

    assert keep_record in verified
    assert already_kept in verified
    assert drop_record not in verified

