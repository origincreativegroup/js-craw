from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Company, FollowUp, Job, SearchCriteria, User


@pytest.mark.asyncio
async def test_model_relationships(db_session):
    user = User(platform="test", email="user@example.com", encrypted_password="secret")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    company = Company(
        name="Example Corp",
        career_page_url="https://example.com/careers",
        crawler_type="generic",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    search = SearchCriteria(
        user_id=user.id,
        name="Python Roles",
        keywords="python",
        location="Remote",
        remote_only=True,
        notify_on_new=True,
        target_companies=[company.id],
    )
    db_session.add(search)
    await db_session.commit()
    await db_session.refresh(search)
    job = Job(
        search_criteria=search,
        company_relation=company,
        external_id="123",
        title="Backend Engineer",
        company="Example Corp",
        location="Remote",
        url="https://example.com/jobs/123",
    )
    follow_up = FollowUp(
        job=job,
        follow_up_date=datetime.utcnow() + timedelta(days=2),
        action_type="email",
        notes="Send resume update",
    )

    db_session.add_all([job, follow_up])
    await db_session.commit()

    result = await db_session.execute(select(Job))
    stored_job = result.scalar_one()

    assert stored_job.company_relation.name == "Example Corp"
    assert stored_job.search_criteria.name == "Python Roles"

    followups = await db_session.execute(select(FollowUp).where(FollowUp.job_id == stored_job.id))
    stored_followup = followups.scalar_one()
    assert stored_followup.action_type == "email"
    assert stored_followup.job_id == stored_job.id

    companies = await db_session.execute(select(Company))
    stored_company = companies.scalar_one()
    assert stored_company.jobs_found_total == 0

    company_jobs = await db_session.execute(
        select(Job).where(Job.company_id == stored_company.id)
    )
    stored_company_job = company_jobs.scalar_one()
    assert stored_company_job.title == "Backend Engineer"
