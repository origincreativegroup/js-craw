"""Entry point for the automated company catalog refresh."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import httpx
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.company_sources import SeedFileCompanySource
from app.services.company_update_pipeline import (
    AICompanyHeuristic,
    CompanyCollector,
    CompanyVerifier,
    run_company_update,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("company_crawl")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("static/company_sources.json"),
        help="Path to the JSON file containing raw company seeds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("companies.csv"),
        help="Destination CSV file to write filtered companies.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=1500,
        help="Maximum number of companies to keep after filtering.",
    )
    return parser


def http_client_factory():
    return httpx.AsyncClient()


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    collector = CompanyCollector(
        sources=[SeedFileCompanySource(args.seed, source_name="seed-file")]
    )

    heuristic = AICompanyHeuristic(http_client_factory=http_client_factory)
    verifier = CompanyVerifier(heuristic=heuristic)

    await run_company_update(
        collector=collector,
        verifier=verifier,
        output_path=args.output,
        cap=args.cap,
    )

    logger.info("Company catalog refresh completed: %s", args.output)


if __name__ == "__main__":
    asyncio.run(main())

