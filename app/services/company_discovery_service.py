"""Service for processing and inserting discovered companies into the database"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal
from app.models import Company, PendingCompany
from app.services.company_update_pipeline import CompanyRecord, AICompanyHeuristic, CompanyVerifier
from app.utils.company_loader import detect_crawler_type, build_crawler_config
from app.config import settings
import httpx

logger = logging.getLogger(__name__)


async def process_and_insert_discovered_companies(
    discovered_companies: List[Dict],
    db: Optional[AsyncSession] = None
) -> Dict:
    """
    Process discovered companies, validate with AI, and insert into database.
    
    Args:
        discovered_companies: List of company dictionaries from discovery
        db: Optional database session (creates new if not provided)
        
    Returns:
        Dictionary with stats about the processing
    """
    should_close_db = False
    if db is None:
        db = AsyncSessionLocal()
        should_close_db = True
    
    try:
        auto_approved = 0
        pending_added = 0
        skipped_existing = 0
        errors = []
        
        # Get existing company names for deduplication
        result = await db.execute(select(Company.name))
        existing_company_names = {row[0].lower() for row in result.fetchall()}
        
        # Get existing pending company names
        pending_result = await db.execute(select(PendingCompany.name).where(PendingCompany.status == "pending"))
        existing_pending_names = {row[0].lower() for row in pending_result.fetchall()}
        
        # Create verifier with AI heuristic
        http_client_factory = lambda: httpx.AsyncClient(timeout=30.0)
        heuristic = AICompanyHeuristic(http_client_factory=http_client_factory)
        verifier = CompanyVerifier(heuristic=heuristic)
        
        # Convert discovered companies to CompanyRecord objects
        company_records = []
        for company_data in discovered_companies:
            company_record = CompanyRecord(
                name=company_data["name"],
                career_page_url=company_data["career_page_url"],
                source=company_data.get("source", "unknown"),
                priority=company_data.get("priority", 50),
                metadata=company_data.get("metadata", {})
            )
            company_records.append(company_record)
        
        # Verify companies with AI
        verified_records = await verifier.verify_many(company_records)
        
        # Process each verified company
        for record in verified_records:
            name_lower = record.name.lower()
            
            # Skip if already exists
            if name_lower in existing_company_names:
                skipped_existing += 1
                continue
            
            if name_lower in existing_pending_names:
                skipped_existing += 1
                continue
            
            try:
                # Determine crawler type
                crawler_type = detect_crawler_type(record.career_page_url)
                crawler_config = build_crawler_config(record.name, record.career_page_url, crawler_type)
                
                # Calculate confidence score based on AI evaluation
                # AICompanyHeuristic returns boolean, so we need to get a score
                confidence_score = await _calculate_confidence_score(record, heuristic)
                
                # Check if should auto-approve
                auto_approve_threshold = getattr(settings, "COMPANY_AUTO_APPROVE_THRESHOLD", 70.0)
                
                if confidence_score >= auto_approve_threshold:
                    # Auto-approve: add directly to Company table
                    company = Company(
                        name=record.name,
                        career_page_url=record.career_page_url,
                        crawler_type=crawler_type,
                        crawler_config=crawler_config,
                        is_active=True,
                        discovery_source=record.source,
                        priority_score=float(record.priority) / 100.0
                    )
                    
                    db.add(company)
                    await db.commit()
                    await db.refresh(company)
                    
                    auto_approved += 1
                    logger.info(f"Auto-approved company: {record.name} (confidence: {confidence_score:.1f}%)")
                else:
                    # Low confidence: add to pending table
                    pending_company = PendingCompany(
                        name=record.name,
                        career_page_url=record.career_page_url,
                        discovery_source=record.source,
                        confidence_score=confidence_score,
                        crawler_type=crawler_type,
                        crawler_config=crawler_config,
                        discovery_metadata=record.metadata,
                        status="pending"
                    )
                    
                    db.add(pending_company)
                    await db.commit()
                    await db.refresh(pending_company)
                    
                    pending_added += 1
                    logger.info(f"Added to pending: {record.name} (confidence: {confidence_score:.1f}%)")
                
                # Update existing sets
                existing_company_names.add(name_lower)
                existing_pending_names.add(name_lower)
                
            except IntegrityError:
                await db.rollback()
                skipped_existing += 1
                logger.debug(f"Company {record.name} already exists, skipping")
            except Exception as e:
                await db.rollback()
                error_msg = f"Error processing company {record.name}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append({"name": record.name, "error": str(e)})
        
        result = {
            "success": True,
            "auto_approved": auto_approved,
            "pending_added": pending_added,
            "skipped_existing": skipped_existing,
            "errors": errors,
            "total_processed": len(verified_records)
        }
        
        logger.info(
            f"Company discovery processing complete: "
            f"{auto_approved} auto-approved, {pending_added} pending, "
            f"{skipped_existing} skipped, {len(errors)} errors"
        )
        
        return result
        
    finally:
        if should_close_db:
            await db.close()


async def _calculate_confidence_score(
    record: CompanyRecord,
    heuristic: AICompanyHeuristic
) -> float:
    """
    Calculate confidence score for a company record.
    
    For now, use a simple heuristic based on AI evaluation and record metadata.
    In the future, this could call AI to get a numeric score.
    """
    try:
        # Get AI evaluation (boolean)
        ai_approves = await heuristic.evaluate(record)
        
        # Start with base score
        if ai_approves:
            base_score = 75.0
        else:
            base_score = 45.0
        
        # Adjust based on source priority
        if record.source == "linkedin":
            base_score += 5.0
        elif record.source == "indeed":
            base_score += 3.0
        elif record.source == "web_search":
            base_score += 2.0
        
        # Adjust based on priority
        if record.priority >= 50:
            base_score += 5.0
        elif record.priority >= 30:
            base_score += 2.0
        
        # Adjust based on URL validity
        url_lower = record.career_page_url.lower()
        if any(path in url_lower for path in ["/careers", "/jobs"]):
            base_score += 3.0
        
        # Clamp between 0 and 100
        return min(100.0, max(0.0, base_score))
        
    except Exception as e:
        logger.warning(f"Error calculating confidence score for {record.name}: {e}")
        return 50.0  # Default medium confidence


async def approve_pending_company(
    pending_id: int,
    db: AsyncSession
) -> Dict:
    """Approve a pending company and move it to Company table"""
    try:
        # Get pending company
        result = await db.execute(
            select(PendingCompany).where(
                PendingCompany.id == pending_id,
                PendingCompany.status == "pending"
            )
        )
        pending = result.scalar_one_or_none()
        
        if not pending:
            return {"success": False, "error": "Pending company not found"}
        
        # Check if company already exists
        existing_result = await db.execute(
            select(Company).where(Company.name == pending.name)
        )
        if existing_result.scalar_one_or_none():
            # Mark pending as approved (but don't create duplicate)
            pending.status = "approved"
            pending.reviewed_at = datetime.utcnow()
            await db.commit()
            return {"success": False, "error": "Company already exists"}
        
        # Create Company from PendingCompany
        company = Company(
            name=pending.name,
            career_page_url=pending.career_page_url,
            crawler_type=pending.crawler_type,
            crawler_config=pending.crawler_config,
            is_active=True,
            discovery_source=pending.discovery_source,
            priority_score=pending.confidence_score / 100.0
        )
        
        db.add(company)
        
        # Update pending status
        pending.status = "approved"
        pending.reviewed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(company)
        
        logger.info(f"Approved pending company: {pending.name} -> Company ID {company.id}")
        
        return {
            "success": True,
            "company_id": company.id,
            "message": "Company approved and added"
        }
        
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Error approving pending company: {e}")
        return {"success": False, "error": f"Database error: {str(e)}"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error approving pending company: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def reject_pending_company(
    pending_id: int,
    db: AsyncSession
) -> Dict:
    """Reject a pending company"""
    try:
        result = await db.execute(
            select(PendingCompany).where(
                PendingCompany.id == pending_id,
                PendingCompany.status == "pending"
            )
        )
        pending = result.scalar_one_or_none()
        
        if not pending:
            return {"success": False, "error": "Pending company not found"}
        
        pending.status = "rejected"
        pending.reviewed_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(f"Rejected pending company: {pending.name}")
        
        return {"success": True, "message": "Company rejected"}
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error rejecting pending company: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
