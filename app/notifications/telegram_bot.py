"""Telegram Bot Agent for interactive job search notifications"""
import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Job, SearchCriteria, CrawlLog, Company
from app.crawler.orchestrator import CrawlerOrchestrator

logger = logging.getLogger(__name__)


class TelegramBotAgent:
    """Interactive Telegram bot for job search notifications"""
    
    def __init__(self, orchestrator: Optional[CrawlerOrchestrator] = None):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.orchestrator = orchestrator
        self.application: Optional[Application] = None
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured - bot will not start")
            return
        
        try:
            # Initialize bot application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Register handlers
            self._register_handlers()
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.application = None
    
    def _register_handlers(self):
        """Register all command and callback handlers"""
        if not self.application:
            return
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("jobs", self._cmd_jobs))
        self.application.add_handler(CommandHandler("stats", self._cmd_stats))
        self.application.add_handler(CommandHandler("search", self._cmd_search))
        self.application.add_handler(CommandHandler("top", self._cmd_top))
        self.application.add_handler(CommandHandler("new", self._cmd_new))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("crawl", self._cmd_crawl))
        self.application.add_handler(CommandHandler("pause", self._cmd_pause))
        self.application.add_handler(CommandHandler("resume", self._cmd_resume))
        
        # Callback query handlers (for inline buttons)
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Message handler for natural language queries (basic)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
    
    async def start_polling(self):
        """Start the bot in polling mode"""
        if not self.application:
            logger.warning("Cannot start bot - not initialized")
            return
        
        try:
            logger.info("Starting Telegram bot in polling mode...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot started and polling for updates")
        except Exception as e:
            logger.error(f"Error starting Telegram bot polling: {e}")
            raise
    
    async def stop_polling(self):
        """Stop the bot"""
        if not self.application:
            return
        
        logger.info("Stopping Telegram bot...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram bot stopped")
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = (
            "👋 *Welcome to Job Search Bot!*\n\n"
            "I can help you:\n"
            "• View new job opportunities\n"
            "• Check statistics and status\n"
            "• Control crawling automation\n"
            "• Search for specific jobs\n\n"
            "Use /help to see all available commands."
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="cmd_stats"),
             InlineKeyboardButton("🆕 New Jobs", callback_data="cmd_new")],
            [InlineKeyboardButton("⭐ Top Jobs", callback_data="cmd_top"),
             InlineKeyboardButton("🔍 Search", callback_data="cmd_search")],
            [InlineKeyboardButton("📈 Status", callback_data="cmd_status"),
             InlineKeyboardButton("❓ Help", callback_data="cmd_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "*Available Commands:*\n\n"
            "📊 */stats* - View dashboard statistics\n"
            "🆕 */new* - Show new jobs (last 24h)\n"
            "⭐ */top* - Show top matched jobs\n"
            "🔍 */search [keywords]* - Search jobs by keywords\n"
            "📈 */status* - Check crawl status\n"
            "🚀 */crawl* - Trigger manual crawl\n"
            "⏸ */pause* - Pause automation\n"
            "▶ */resume* - Resume automation\n\n"
            "You can also use inline buttons for quick actions!"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            async with AsyncSessionLocal() as db:
                # Total jobs
                result = await db.execute(select(func.count(Job.id)))
                total_jobs = result.scalar() or 0
                
                # New jobs (last 24 hours)
                yesterday = datetime.utcnow() - timedelta(days=1)
                result = await db.execute(
                    select(func.count(Job.id)).where(Job.discovered_at >= yesterday)
                )
                new_jobs_24h = result.scalar() or 0
                
                # Jobs by status
                result = await db.execute(select(Job))
                all_jobs = result.scalars().all()
                by_status = {}
                for job in all_jobs:
                    status_val = job.status or "new"
                    by_status[status_val] = by_status.get(status_val, 0) + 1
                
                # Active searches
                result = await db.execute(
                    select(func.count(SearchCriteria.id)).where(SearchCriteria.is_active == True)
                )
                active_searches = result.scalar() or 0
                
                stats_msg = (
                    "*📊 Dashboard Statistics*\n\n"
                    f"📋 Total Jobs: *{total_jobs}*\n"
                    f"🆕 New (24h): *{new_jobs_24h}*\n"
                    f"🔍 Active Searches: *{active_searches}*\n\n"
                    "*Jobs by Status:*\n"
                )
                
                for status, count in sorted(by_status.items()):
                    emoji = {
                        "new": "🆕",
                        "viewed": "👁",
                        "applied": "✅",
                        "saved": "💾",
                        "rejected": "❌"
                    }.get(status, "📄")
                    stats_msg += f"{emoji} {status}: *{count}*\n"
                
                keyboard = [
                    [InlineKeyboardButton("🆕 New Jobs", callback_data="cmd_new")],
                    [InlineKeyboardButton("⭐ Top Jobs", callback_data="cmd_top")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    stats_msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            await update.message.reply_text(f"❌ Error getting statistics: {str(e)}")
    
    async def _cmd_jobs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /jobs command - show recent jobs"""
        try:
            limit = 10
            if context.args and context.args[0].isdigit():
                limit = min(int(context.args[0]), 20)  # Max 20
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Job)
                    .order_by(desc(Job.discovered_at))
                    .limit(limit)
                )
                jobs = result.scalars().all()
                
                if not jobs:
                    await update.message.reply_text("📭 No jobs found.")
                    return
                
                msg = f"*📋 Recent Jobs ({len(jobs)})*\n\n"
                
                for job in jobs[:5]:  # Show first 5 in message
                    match_emoji = "⭐" if job.ai_match_score and job.ai_match_score >= 75 else "📄"
                    match_text = f" {job.ai_match_score:.0f}% match" if job.ai_match_score else ""
                    status_emoji = {"new": "🆕", "viewed": "👁", "applied": "✅"}.get(job.status, "📄")
                    
                    msg += (
                        f"{match_emoji} *{job.title}*\n"
                        f"🏢 {job.company}\n"
                        f"📍 {job.location or 'Remote'}\n"
                        f"{status_emoji} {job.status}{match_text}\n\n"
                    )
                
                if len(jobs) > 5:
                    msg += f"... and {len(jobs) - 5} more jobs"
                
                # Add inline buttons for top jobs
                keyboard = [
                    [InlineKeyboardButton("⭐ Top Matched", callback_data="cmd_top")],
                    [InlineKeyboardButton("🆕 New Only", callback_data="cmd_new")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error getting jobs: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /new command - show new jobs"""
        try:
            async with AsyncSessionLocal() as db:
                yesterday = datetime.utcnow() - timedelta(days=1)
                result = await db.execute(
                    select(Job)
                    .where(Job.is_new == True)
                    .order_by(desc(Job.discovered_at))
                    .limit(10)
                )
                jobs = result.scalars().all()
                
                if not jobs:
                    await update.message.reply_text("📭 No new jobs in the last 24 hours.")
                    return
                
                msg = f"*🆕 New Jobs ({len(jobs)})*\n\n"
                
                buttons = []
                for job in jobs[:5]:
                    match_text = f" {job.ai_match_score:.0f}%" if job.ai_match_score else ""
                    msg += (
                        f"*{job.title}*\n"
                        f"🏢 {job.company} | 📍 {job.location or 'Remote'}{match_text}\n\n"
                    )
                    # Add button for each job
                    buttons.append([
                        InlineKeyboardButton(
                            f"📄 {job.title[:30]}...",
                            callback_data=f"job_{job.id}"
                        )
                    ])
                
                if len(jobs) > 5:
                    msg += f"... and {len(jobs) - 5} more new jobs"
                
                reply_markup = InlineKeyboardMarkup(buttons[:5]) if buttons else None
                
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error getting new jobs: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /top command - show top matched jobs"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Job)
                    .where(Job.ai_match_score.isnot(None))
                    .where(Job.ai_match_score >= 70)
                    .order_by(desc(Job.ai_match_score))
                    .limit(10)
                )
                jobs = result.scalars().all()
                
                if not jobs:
                    await update.message.reply_text("⭐ No highly matched jobs found (match score >= 70%).")
                    return
                
                msg = f"*⭐ Top Matched Jobs ({len(jobs)})*\n\n"
                
                buttons = []
                for job in jobs[:5]:
                    msg += (
                        f"⭐ *{job.title}* - {job.ai_match_score:.0f}% match\n"
                        f"🏢 {job.company} | 📍 {job.location or 'Remote'}\n\n"
                    )
                    buttons.append([
                        InlineKeyboardButton(
                            f"⭐ {job.ai_match_score:.0f}% - {job.title[:25]}...",
                            callback_data=f"job_{job.id}"
                        )
                    ])
                
                if len(jobs) > 5:
                    msg += f"... and {len(jobs) - 5} more top matches"
                
                reply_markup = InlineKeyboardMarkup(buttons[:5]) if buttons else None
                
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error getting top jobs: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text(
                "🔍 *Usage:* /search [keywords]\n\n"
                "Example: /search python remote",
                parse_mode="Markdown"
            )
            return
        
        try:
            keywords = " ".join(context.args).lower()
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Job)
                    .where(
                        Job.title.ilike(f"%{keywords}%") |
                        Job.description.ilike(f"%{keywords}%") |
                        Job.company.ilike(f"%{keywords}%")
                    )
                    .order_by(desc(Job.discovered_at))
                    .limit(10)
                )
                jobs = result.scalars().all()
                
                if not jobs:
                    await update.message.reply_text(
                        f"📭 No jobs found matching '{keywords}'"
                    )
                    return
                
                msg = f"*🔍 Search Results: '{keywords}' ({len(jobs)})*\n\n"
                
                buttons = []
                for job in jobs[:5]:
                    match_text = f" {job.ai_match_score:.0f}%" if job.ai_match_score else ""
                    msg += (
                        f"*{job.title}*\n"
                        f"🏢 {job.company} | 📍 {job.location or 'Remote'}{match_text}\n\n"
                    )
                    buttons.append([
                        InlineKeyboardButton(
                            f"📄 {job.title[:30]}...",
                            callback_data=f"job_{job.id}"
                        )
                    ])
                
                if len(jobs) > 5:
                    msg += f"... and {len(jobs) - 5} more results"
                
                reply_markup = InlineKeyboardMarkup(buttons[:5]) if buttons else None
                
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error searching jobs: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show crawl status"""
        try:
            async with AsyncSessionLocal() as db:
                # Check for running crawls
                result = await db.execute(
                    select(CrawlLog).where(CrawlLog.status == 'running')
                )
                running_logs = result.scalars().all()
                
                # Get recent crawl logs
                result = await db.execute(
                    select(CrawlLog)
                    .order_by(desc(CrawlLog.started_at))
                    .limit(5)
                )
                recent_logs = result.scalars().all()
                
                is_running = len(running_logs) > 0
                status_emoji = "🟢" if not is_running else "🟡"
                
                msg = f"{status_emoji} *Crawl Status*\n\n"
                
                if is_running:
                    msg += f"🔄 *Running:* {len(running_logs)} active crawl(s)\n\n"
                else:
                    msg += "✅ *Status:* Idle\n\n"
                
                msg += "*Recent Crawls:*\n"
                for log in recent_logs[:5]:
                    status_icon = {
                        "completed": "✅",
                        "running": "🔄",
                        "failed": "❌"
                    }.get(log.status, "📄")
                    
                    duration = ""
                    if log.completed_at and log.started_at:
                        duration_sec = (log.completed_at - log.started_at).total_seconds()
                        duration = f" ({duration_sec:.0f}s)"
                    
                    msg += (
                        f"{status_icon} {log.status.title()}: "
                        f"{log.jobs_found} jobs, {log.new_jobs} new{duration}\n"
                    )
                
                keyboard = [
                    [InlineKeyboardButton("🚀 Run Crawl", callback_data="cmd_crawl")],
                    [InlineKeyboardButton("📊 Stats", callback_data="cmd_stats")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_crawl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /crawl command - trigger manual crawl"""
        if not self.orchestrator:
            await update.message.reply_text(
                "❌ Crawler orchestrator not available. Use the web dashboard to trigger crawls."
            )
            return
        
        try:
            await update.message.reply_text("🚀 Starting manual crawl...")
            
            # Run crawl in background
            results = await self.orchestrator.run_all_searches()
            
            msg = (
                f"✅ *Crawl Completed*\n\n"
                f"📊 Found *{len(results)}* new job(s)"
            )
            
            keyboard = [
                [InlineKeyboardButton("🆕 View New Jobs", callback_data="cmd_new")],
                [InlineKeyboardButton("📊 Stats", callback_data="cmd_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error running crawl: {e}")
            await update.message.reply_text(
                f"❌ Error running crawl: {str(e)}\n\n"
                "Note: Use the web dashboard for full crawl control."
            )
    
    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command"""
        # This would need access to the scheduler
        await update.message.reply_text(
            "⏸ *Pause Automation*\n\n"
            "Use the web dashboard to pause/resume automation.",
            parse_mode="Markdown"
        )
    
    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        await update.message.reply_text(
            "▶ *Resume Automation*\n\n"
            "Use the web dashboard to pause/resume automation.",
            parse_mode="Markdown"
        )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("cmd_"):
            # Command callbacks
            cmd = data.replace("cmd_", "")
            if cmd == "stats":
                await self._cmd_stats(update, context)
            elif cmd == "new":
                await self._cmd_new(update, context)
            elif cmd == "top":
                await self._cmd_top(update, context)
            elif cmd == "search":
                await query.message.reply_text(
                    "🔍 *Search Jobs*\n\n"
                    "Send: /search [keywords]",
                    parse_mode="Markdown"
                )
            elif cmd == "status":
                await self._cmd_status(update, context)
            elif cmd == "crawl":
                await self._cmd_crawl(update, context)
            elif cmd == "help":
                await self._cmd_help(update, context)
        
        elif data.startswith("job_"):
            # Job detail callback
            job_id = int(data.replace("job_", ""))
            await self._show_job_detail(query, job_id)
        
        elif data.startswith("action_"):
            # Job action callbacks (view, apply, save)
            parts = data.split("_")
            if len(parts) >= 3:
                action = parts[1]
                job_id = int(parts[2])
                await self._handle_job_action(query, action, job_id)
    
    async def _show_job_detail(self, query, job_id: int):
        """Show detailed job information"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                
                if not job:
                    await query.message.reply_text("❌ Job not found")
                    return
                
                msg = (
                    f"*{job.title}*\n\n"
                    f"🏢 *Company:* {job.company}\n"
                    f"📍 *Location:* {job.location or 'Remote'}\n"
                )
                
                if job.ai_match_score:
                    match_emoji = "⭐" if job.ai_match_score >= 75 else "📊"
                    msg += f"{match_emoji} *Match Score:* {job.ai_match_score:.0f}%\n"
                
                if job.ai_summary:
                    msg += f"\n📝 *Summary:*\n{job.ai_summary[:200]}\n"
                
                if job.ai_pros:
                    msg += f"\n✅ *Pros:*\n"
                    for pro in job.ai_pros[:3]:
                        msg += f"• {pro}\n"
                
                msg += f"\n🔗 [View Job]({job.url})"
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Applied", callback_data=f"action_apply_{job_id}"),
                        InlineKeyboardButton("💾 Save", callback_data=f"action_save_{job_id}")
                    ],
                    [InlineKeyboardButton("🔙 Back to Jobs", callback_data="cmd_new")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text(
                    msg,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
        except Exception as e:
            logger.error(f"Error showing job detail: {e}")
            await query.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _handle_job_action(self, query, action: str, job_id: int):
        """Handle job actions (apply, save, etc.)"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                
                if not job:
                    await query.answer("Job not found", show_alert=True)
                    return
                
                if action == "apply":
                    job.status = "applied"
                    await query.answer("✅ Marked as applied!")
                elif action == "save":
                    job.status = "saved"
                    await query.answer("💾 Job saved!")
                
                await db.commit()
                
                # Update message
                await query.message.edit_text(
                    f"✅ *Action completed*\n\n"
                    f"Job: {job.title}\n"
                    f"Status: {job.status}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error handling job action: {e}")
            await query.answer("❌ Error updating job", show_alert=True)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages (basic implementation)"""
        text = update.message.text.lower()
        
        # Simple keyword matching
        if any(word in text for word in ["new", "recent", "latest"]):
            await self._cmd_new(update, context)
        elif any(word in text for word in ["top", "best", "match"]):
            await self._cmd_top(update, context)
        elif any(word in text for word in ["stats", "statistics", "summary"]):
            await self._cmd_stats(update, context)
        elif any(word in text for word in ["status", "running", "crawl"]):
            await self._cmd_status(update, context)
        else:
            # Default to search
            context.args = text.split()
            await self._cmd_search(update, context)
    
    async def send_rich_notification(
        self,
        title: str,
        message: str,
        jobs: Optional[List[Job]] = None,
        buttons: Optional[List[List[InlineKeyboardButton]]] = None
    ) -> bool:
        """Send rich notification with inline buttons"""
        if not self.application or not self.chat_id:
            return False
        
        try:
            text = f"*{title}*\n\n{message}"
            
            # Add job buttons if provided
            if jobs and not buttons:
                buttons = []
                for job in jobs[:3]:  # Max 3 buttons
                    buttons.append([
                        InlineKeyboardButton(
                            f"📄 {job.title[:30]}...",
                            callback_data=f"job_{job.id}"
                        )
                    ])
            
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
            return True
        except Exception as e:
            logger.error(f"Error sending rich notification: {e}")
            return False

