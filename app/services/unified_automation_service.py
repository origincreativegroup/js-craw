"""Unified automation service that aggregates automation controls and company data"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models import Company, CrawlLog, PendingCompany
from app.config import settings

logger = logging.getLogger(__name__)


class UnifiedAutomationService:
    """Service that unifies automation controls and company data"""
    
    def __init__(self, scheduler, orchestrator):
        self.scheduler = scheduler
        self.orchestrator = orchestrator
    
    async def get_unified_status(
        self,
        db: AsyncSession,
        limit_logs: int = 10
    ) -> Dict:
        """
        Get complete unified status combining automation and company data
        
        Returns:
            Dict containing:
            - automation: scheduler, crawl status, discovery status
            - companies: overview, health summary
            - recent_activity: last crawl logs, recent discoveries
            - metrics: combined success rates, averages
        """
        try:
            # Get automation state
            automation = await self._get_automation_state(db, limit_logs)
            
            # Get company summary
            company_summary = await self._get_company_summary(db)
            
            # Get recent activity
            recent_activity = await self._get_recent_activity(db, limit_logs)
            
            # Get combined metrics
            metrics = await self._get_combined_metrics(db)
            
            return {
                "automation": automation,
                "companies": company_summary,
                "recent_activity": recent_activity,
                "metrics": metrics,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting unified status: {e}", exc_info=True)
            raise
    
    async def get_unified_companies(
        self,
        db: AsyncSession,
        active_only: bool = False
    ) -> List[Dict]:
        """
        Get companies with their automation state (last crawl, health, priority)
        
        Args:
            db: Database session
            active_only: If True, only return active companies
            
        Returns:
            List of companies with automation metadata
        """
        try:
            query = select(Company).order_by(Company.priority_score.desc(), Company.name)
            if active_only:
                query = query.where(Company.is_active == True)
            
            result = await db.execute(query)
            companies = result.scalars().all()
            
            # Get last crawl log for each company
            company_ids = [c.id for c in companies]
            if company_ids:
                # Get most recent crawl log per company
                crawl_logs_query = select(
                    CrawlLog.company_id,
                    func.max(CrawlLog.started_at).label('last_crawl_at')
                ).where(
                    CrawlLog.company_id.in_(company_ids)
                ).group_by(CrawlLog.company_id)
                
                crawl_logs_result = await db.execute(crawl_logs_query)
                last_crawl_map = {
                    row.company_id: row.last_crawl_at
                    for row in crawl_logs_result.fetchall()
                }
                
                # Get crawl success stats per company
                success_stats_query = select(
                    CrawlLog.company_id,
                    func.count(CrawlLog.id).label('total_crawls'),
                    func.sum(func.cast(CrawlLog.status == 'completed', func.Integer)).label('successful_crawls')
                ).where(
                    CrawlLog.company_id.in_(company_ids),
                    CrawlLog.started_at >= datetime.utcnow() - timedelta(days=30)
                ).group_by(CrawlLog.company_id)
                
                stats_result = await db.execute(success_stats_query)
                stats_map = {
                    row.company_id: {
                        'total_crawls': row.total_crawls or 0,
                        'successful_crawls': row.successful_crawls or 0
                    }
                    for row in stats_result.fetchall()
                }
            else:
                last_crawl_map = {}
                stats_map = {}
            
            unified_companies = []
            for company in companies:
                last_crawl_at = last_crawl_map.get(company.id)
                stats = stats_map.get(company.id, {'total_crawls': 0, 'successful_crawls': 0})
                
                # Calculate success rate
                success_rate = (
                    (stats['successful_crawls'] / stats['total_crawls'] * 100)
                    if stats['total_crawls'] > 0 else None
                )
                
                # Determine health status
                health_status = self._determine_company_health(
                    company,
                    success_rate,
                    stats['total_crawls']
                )
                
                unified_companies.append({
                    "id": company.id,
                    "name": company.name,
                    "career_page_url": company.career_page_url,
                    "crawler_type": company.crawler_type,
                    "crawler_config": company.crawler_config,
                    "is_active": company.is_active,
                    "last_crawled_at": company.last_crawled_at.isoformat() if company.last_crawled_at else None,
                    "last_crawl_at": last_crawl_at.isoformat() if last_crawl_at else None,
                    "jobs_found_total": company.jobs_found_total,
                    "created_at": company.created_at.isoformat(),
                    "updated_at": company.updated_at.isoformat(),
                    "consecutive_empty_crawls": company.consecutive_empty_crawls,
                    "viability_score": company.viability_score,
                    "viability_last_checked": company.viability_last_checked.isoformat() if company.viability_last_checked else None,
                    "discovery_source": company.discovery_source,
                    "last_successful_crawl": company.last_successful_crawl.isoformat() if company.last_successful_crawl else None,
                    "priority_score": company.priority_score,
                    # Automation metadata
                    "automation": {
                        "total_crawls_30d": stats['total_crawls'],
                        "successful_crawls_30d": stats['successful_crawls'],
                        "success_rate": round(success_rate, 1) if success_rate is not None else None,
                        "health_status": health_status,
                        "needs_attention": (
                            company.consecutive_empty_crawls >= 2 or
                            (success_rate is not None and success_rate < 70) or
                            (company.viability_score is not None and company.viability_score < 50)
                        )
                    }
                })
            
            return unified_companies
        except Exception as e:
            logger.error(f"Error getting unified companies: {e}", exc_info=True)
            raise
    
    async def _get_automation_state(
        self,
        db: AsyncSession,
        limit_logs: int
    ) -> Dict:
        """Get automation state (scheduler, crawl status, discovery)"""
        # Get scheduler status
        scheduler_status = self._get_scheduler_status()
        
        # Get crawl status
        crawl_status = await self._get_crawl_status(db, limit_logs)
        
        # Get discovery status
        discovery_status = await self._get_discovery_status(db)
        
        return {
            "scheduler": scheduler_status,
            "crawler": crawl_status,
            "discovery": discovery_status
        }
    
    def _get_scheduler_status(self) -> Dict:
        """Get scheduler status"""
        try:
            job = self.scheduler.get_job("crawl_all_companies")
            
            if not job:
                return {
                    "status": "not_configured",
                    "next_run": None,
                    "interval_minutes": None,
                    "is_paused": True
                }
            
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            
            return {
                "status": "running" if self.scheduler.running else "stopped",
                "next_run": next_run,
                "interval_minutes": settings.CRAWL_INTERVAL_MINUTES,
                "is_paused": job.next_run_time is None,
                "job_id": job.id,
                "job_name": job.name
            }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_crawl_status(
        self,
        db: AsyncSession,
        limit_logs: int
    ) -> Dict:
        """Get crawl status"""
        try:
            # Get recent crawl logs
            result = await db.execute(
                select(CrawlLog)
                .order_by(desc(CrawlLog.started_at))
                .limit(limit_logs)
            )
            logs = result.scalars().all()
            
            # Check for running crawls
            running_result = await db.execute(
                select(CrawlLog).where(CrawlLog.status == 'running')
            )
            running_logs = running_result.scalars().all()
            
            # Get orchestrator progress
            progress = self.orchestrator.get_current_progress()
            
            # Get crawler health metrics
            health_metrics = await self._get_crawler_health_metrics(db, logs)
            
            return {
                "is_running": len(running_logs) > 0,
                "running_count": len(running_logs),
                "queue_length": progress.get('queue_length', 0),
                "current_company": progress.get('current_company'),
                "progress": progress.get('progress', {'current': 0, 'total': 0}),
                "eta_seconds": progress.get('eta_seconds'),
                "run_type": progress.get('run_type'),
                "recent_logs": [
                    {
                        "id": log.id,
                        "company_id": log.company_id,
                        "search_criteria_id": log.search_criteria_id,
                        "platform": log.platform,
                        "status": log.status,
                        "started_at": log.started_at.isoformat() if log.started_at else None,
                        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                        "jobs_found": log.jobs_found,
                        "new_jobs": log.new_jobs,
                        "error_message": log.error_message,
                        "duration_seconds": (
                            (log.completed_at - log.started_at).total_seconds()
                            if log.completed_at and log.started_at else None
                        )
                    }
                    for log in logs
                ],
                "crawler_health": health_metrics
            }
        except Exception as e:
            logger.error(f"Error getting crawl status: {e}", exc_info=True)
            return {
                "is_running": False,
                "error": str(e)
            }
    
    async def _get_crawler_health_metrics(
        self,
        db: AsyncSession,
        logs: List[CrawlLog]
    ) -> Dict:
        """Calculate crawler health metrics from logs"""
        try:
            crawler_type_stats = {}
            
            for log in logs[:50]:  # Analyze last 50 logs
                if log.company_id:
                    company_result = await db.execute(
                        select(Company).where(Company.id == log.company_id)
                    )
                    company = company_result.scalar_one_or_none()
                    if company:
                        crawler_class = self.orchestrator.get_crawler_type_classification(company.crawler_type)
                        if crawler_class not in crawler_type_stats:
                            crawler_type_stats[crawler_class] = {
                                'total': 0,
                                'success': 0,
                                'failed': 0,
                                'avg_duration': 0
                            }
                        crawler_type_stats[crawler_class]['total'] += 1
                        if log.status == 'completed':
                            crawler_type_stats[crawler_class]['success'] += 1
                        elif log.status == 'failed':
                            crawler_type_stats[crawler_class]['failed'] += 1
                        if log.completed_at and log.started_at:
                            duration = (log.completed_at - log.started_at).total_seconds()
                            current_avg = crawler_type_stats[crawler_class]['avg_duration']
                            count = crawler_type_stats[crawler_class]['total']
                            crawler_type_stats[crawler_class]['avg_duration'] = (
                                (current_avg * (count - 1) + duration) / count
                            )
            
            # Calculate health metrics
            health_metrics = {}
            for crawler_type, stats in crawler_type_stats.items():
                success_rate = (
                    (stats['success'] / stats['total'] * 100)
                    if stats['total'] > 0 else 0
                )
                health_metrics[crawler_type] = {
                    'success_rate': round(success_rate, 1),
                    'avg_duration_seconds': round(stats['avg_duration'], 1),
                    'error_count': stats['failed'],
                    'total_runs': stats['total']
                }
            
            return health_metrics
        except Exception as e:
            logger.error(f"Error calculating crawler health metrics: {e}", exc_info=True)
            return {}
    
    async def _get_discovery_status(self, db: AsyncSession) -> Dict:
        """Get company discovery status"""
        try:
            from app.utils.company_loader import count_companies
            
            # Get company counts
            total_companies = await count_companies(db, active_only=False)
            active_companies = await count_companies(db, active_only=True)
            
            # Get pending companies
            pending_result = await db.execute(
                select(func.count(PendingCompany.id)).where(PendingCompany.status == "pending")
            )
            pending_count = pending_result.scalar() or 0
            
            # Get recent pending companies
            recent_pending_result = await db.execute(
                select(PendingCompany)
                .where(PendingCompany.status == "pending")
                .order_by(desc(PendingCompany.created_at))
                .limit(5)
            )
            recent_pending = recent_pending_result.scalars().all()
            
            return {
                "total_companies": total_companies,
                "active_companies": active_companies,
                "target_companies": getattr(settings, "COMPANY_TARGET_COUNT", 4000),
                "pending_count": pending_count,
                "discovery_enabled": getattr(settings, "COMPANY_DISCOVERY_ENABLED", True),
                "discovery_interval_hours": getattr(settings, "COMPANY_DISCOVERY_INTERVAL_HOURS", 6),
                "auto_approve_threshold": getattr(settings, "COMPANY_AUTO_APPROVE_THRESHOLD", 70.0),
                "recent_pending": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "career_page_url": p.career_page_url,
                        "discovery_source": p.discovery_source,
                        "confidence_score": p.confidence_score,
                        "created_at": p.created_at.isoformat()
                    }
                    for p in recent_pending
                ]
            }
        except Exception as e:
            logger.error(f"Error getting discovery status: {e}", exc_info=True)
            return {
                "error": str(e)
            }
    
    async def _get_company_summary(self, db: AsyncSession) -> Dict:
        """Get company overview and health summary"""
        try:
            # Total companies
            result = await db.execute(select(func.count(Company.id)))
            total = result.scalar() or 0
            
            # Active companies
            result = await db.execute(
                select(func.count(Company.id)).where(Company.is_active == True)
            )
            active = result.scalar() or 0
            
            # Companies with high consecutive empty crawls
            result = await db.execute(
                select(func.count(Company.id)).where(
                    Company.is_active == True,
                    Company.consecutive_empty_crawls >= 2
                )
            )
            needs_attention = result.scalar() or 0
            
            # Companies needing viability check
            result = await db.execute(
                select(func.count(Company.id)).where(
                    Company.is_active == True,
                    Company.viability_last_checked.is_(None)
                )
            )
            unchecked = result.scalar() or 0
            
            # Average viability score
            result = await db.execute(
                select(func.avg(Company.viability_score)).where(
                    Company.is_active == True,
                    Company.viability_score.isnot(None)
                )
            )
            avg_viability = result.scalar() or 0.0
            
            return {
                "total_companies": total,
                "active_companies": active,
                "inactive_companies": total - active,
                "needs_attention": needs_attention,
                "unchecked_viability": unchecked,
                "average_viability_score": round(avg_viability, 2) if avg_viability else None
            }
        except Exception as e:
            logger.error(f"Error getting company summary: {e}", exc_info=True)
            return {
                "error": str(e)
            }
    
    async def _get_recent_activity(
        self,
        db: AsyncSession,
        limit_logs: int
    ) -> Dict:
        """Get recent activity (crawl logs, discoveries)"""
        try:
            # Get recent crawl logs
            result = await db.execute(
                select(CrawlLog)
                .order_by(desc(CrawlLog.started_at))
                .limit(limit_logs)
            )
            logs = result.scalars().all()
            
            # Get recent pending companies
            pending_result = await db.execute(
                select(PendingCompany)
                .where(PendingCompany.status == "pending")
                .order_by(desc(PendingCompany.created_at))
                .limit(5)
            )
            recent_pending = pending_result.scalars().all()
            
            return {
                "recent_crawls": [
                    {
                        "id": log.id,
                        "company_id": log.company_id,
                        "status": log.status,
                        "started_at": log.started_at.isoformat() if log.started_at else None,
                        "jobs_found": log.jobs_found,
                        "new_jobs": log.new_jobs
                    }
                    for log in logs
                ],
                "recent_discoveries": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "discovery_source": p.discovery_source,
                        "confidence_score": p.confidence_score,
                        "created_at": p.created_at.isoformat()
                    }
                    for p in recent_pending
                ]
            }
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}", exc_info=True)
            return {
                "error": str(e)
            }
    
    async def _get_combined_metrics(self, db: AsyncSession) -> Dict:
        """Get combined metrics across automation and companies"""
        try:
            # Get crawl success rate from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(
                    func.count(CrawlLog.id).label('total'),
                    func.sum(func.cast(CrawlLog.status == 'completed', func.Integer)).label('successful')
                ).where(
                    CrawlLog.started_at >= thirty_days_ago
                )
            )
            row = result.fetchone()
            total_crawls = row.total or 0
            successful_crawls = row.successful or 0
            success_rate = (
                (successful_crawls / total_crawls * 100)
                if total_crawls > 0 else None
            )
            
            # Get average crawl duration
            result = await db.execute(
                select(
                    func.avg(
                        func.extract('epoch', CrawlLog.completed_at - CrawlLog.started_at)
                    ).label('avg_duration')
                ).where(
                    CrawlLog.status == 'completed',
                    CrawlLog.completed_at.isnot(None),
                    CrawlLog.started_at >= thirty_days_ago
                )
            )
            avg_duration = result.scalar() or 0
            
            return {
                "crawl_success_rate_30d": round(success_rate, 1) if success_rate is not None else None,
                "total_crawls_30d": total_crawls,
                "successful_crawls_30d": successful_crawls,
                "average_crawl_duration_seconds": round(avg_duration, 1) if avg_duration else None
            }
        except Exception as e:
            logger.error(f"Error getting combined metrics: {e}", exc_info=True)
            return {
                "error": str(e)
            }
    
    def _determine_company_health(
        self,
        company: Company,
        success_rate: Optional[float],
        total_crawls: int
    ) -> str:
        """Determine company health status"""
        if not company.is_active:
            return "inactive"
        
        if company.consecutive_empty_crawls >= 3:
            return "critical"
        
        if company.consecutive_empty_crawls >= 2:
            return "warning"
        
        if success_rate is not None and success_rate < 50:
            return "warning"
        
        if company.viability_score is not None and company.viability_score < 50:
            return "warning"
        
        if total_crawls == 0:
            return "unknown"
        
        return "healthy"

