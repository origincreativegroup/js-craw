"""Migration script to add pipeline_stage to existing jobs and consolidate AI content"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.database import async_session_maker, init_db
from app.models import Job, GeneratedDocument


async def migrate_pipeline_stages():
    """Migrate existing jobs to pipeline stages based on their status"""
    async with async_session_maker() as db:
        try:
            # Get all jobs without pipeline_stage or with null pipeline_stage
            result = await db.execute(
                select(Job).where(
                    (Job.pipeline_stage.is_(None)) | (Job.pipeline_stage == "")
                )
            )
            jobs = result.scalars().all()
            
            print(f"Found {len(jobs)} jobs to migrate")
            
            # Map status to pipeline stage
            status_to_stage = {
                "new": "discover",
                "viewed": "review",
                "applied": "apply",
                "rejected": "archive",
                "saved": "review",
                "archived": "archive",
            }
            
            migrated_count = 0
            for job in jobs:
                # Determine pipeline stage from status
                stage = status_to_stage.get(job.status, "discover")
                
                # If job has an application, move to apply stage
                if job.applications:
                    stage = "apply"
                # If job has tasks, might be in prepare or apply
                elif job.tasks:
                    # Check if any tasks are for application
                    if any(t.task_type == "apply" for t in job.tasks):
                        stage = "prepare"
                    else:
                        stage = "review"
                # If job has follow-ups, move to follow_up stage
                elif job.follow_ups:
                    stage = "follow_up"
                
                job.pipeline_stage = stage
                migrated_count += 1
            
            await db.commit()
            print(f"Migrated {migrated_count} jobs to pipeline stages")
            
        except Exception as e:
            await db.rollback()
            print(f"Error migrating pipeline stages: {e}")
            raise


async def consolidate_ai_content():
    """Consolidate AI analysis fields into ai_content JSON field"""
    async with async_session_maker() as db:
        try:
            result = await db.execute(
                select(Job).where(Job.ai_content.is_(None))
            )
            jobs = result.scalars().all()
            
            print(f"Found {len(jobs)} jobs to consolidate AI content")
            
            consolidated_count = 0
            for job in jobs:
                # Only consolidate if there's AI data
                if job.ai_summary or job.ai_pros or job.ai_cons or job.ai_keywords_matched:
                    ai_content = {
                        "summary": job.ai_summary,
                        "pros": job.ai_pros or [],
                        "cons": job.ai_cons or [],
                        "keywords_matched": job.ai_keywords_matched or [],
                        "match_score": job.ai_match_score,
                        "recommended": job.ai_recommended,
                    }
                    job.ai_content = ai_content
                    consolidated_count += 1
            
            await db.commit()
            print(f"Consolidated AI content for {consolidated_count} jobs")
            
        except Exception as e:
            await db.rollback()
            print(f"Error consolidating AI content: {e}")
            raise


async def migrate_document_versions():
    """Add version tracking to existing generated documents"""
    async with async_session_maker() as db:
        try:
            # Get all generated documents
            result = await db.execute(select(GeneratedDocument))
            documents = result.scalars().all()
            
            print(f"Found {len(documents)} documents to migrate")
            
            # Group by job_id and document_type
            from collections import defaultdict
            docs_by_job_type = defaultdict(list)
            for doc in documents:
                key = (doc.job_id, doc.document_type)
                docs_by_job_type[key].append(doc)
            
            migrated_count = 0
            for (job_id, doc_type), docs in docs_by_job_type.items():
                # Sort by generated_at
                docs_sorted = sorted(docs, key=lambda d: d.generated_at or datetime.min)
                
                # Assign versions (oldest = version 1)
                for i, doc in enumerate(docs_sorted, 1):
                    if doc.version is None or doc.version == 0:
                        doc.version = i
                    # Mark latest as current
                    if i == len(docs_sorted):
                        doc.is_current = True
                    else:
                        doc.is_current = False
                    migrated_count += 1
            
            await db.commit()
            print(f"Migrated {migrated_count} documents with version tracking")
            
        except Exception as e:
            await db.rollback()
            print(f"Error migrating document versions: {e}")
            raise


async def main():
    """Run all migrations"""
    print("Starting pipeline migration...")
    await init_db()
    
    print("\n1. Migrating pipeline stages...")
    await migrate_pipeline_stages()
    
    print("\n2. Consolidating AI content...")
    await consolidate_ai_content()
    
    print("\n3. Migrating document versions...")
    await migrate_document_versions()
    
    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(main())

