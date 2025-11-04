import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Company, SearchCriteria


@pytest.mark.asyncio
async def test_create_search_missing_company(api_client: AsyncClient):
    payload = {
        "name": "Missing Company Search",
        "keywords": "python",
        "target_companies": [9999],
    }

    response = await api_client.post("/api/searches", json=payload)
    assert response.status_code == 400
    assert "Companies not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_search_success(api_client: AsyncClient, session_factory):
    async with session_factory() as session:
        company = Company(
            name="Test Company",
            career_page_url="https://example.com/careers",
            crawler_type="generic",
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        company_id = company.id

    payload = {
        "name": "Valid Search",
        "keywords": "python",
        "location": "Remote",
        "remote_only": True,
        "target_companies": [company_id],
        "notify_on_new": True,
    }

    response = await api_client.post("/api/searches", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Search criteria created"
    created_id = body["id"]

    async with session_factory() as session:
        result = await session.execute(select(SearchCriteria).where(SearchCriteria.id == created_id))
        stored = result.scalar_one()

    assert stored.name == "Valid Search"
    assert stored.target_companies == [company_id]
