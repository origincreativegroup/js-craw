# Job Search Crawler - Complete System

## 🎉 What You've Got

A fully functional, production-ready job search automation system with:

✅ **Automated Crawling**: ALL active companies every 30 minutes (Greenhouse, Lever, Generic, Indeed, LinkedIn)
✅ **AI Analysis**: Local LLM (Ollama) for intelligent job matching and ranking
  - Continuous AI ranking every 60 minutes
  - Daily top 5 job selection at 3 PM
✅ **AI Document Generation**: Automatically generates tailored resumes and cover letters for top jobs daily
✅ **React TypeScript Frontend**: Modern, component-based UI with real-time updates
✅ **Mobile Notifications**: Push alerts via ntfy, Pushover, or Telegram
✅ **Web Dashboard**: Clean, responsive UI for managing everything
✅ **Secure Storage**: Encrypted credentials, PostgreSQL database
✅ **Docker-Based**: One-command deployment
✅ **OpenWebUI**: Bonus AI chat interface

## 📦 What's Included

### Core Components
- **FastAPI Backend**: RESTful API server
- **Selenium Automation**: Browser automation for LinkedIn/Indeed
- **Ollama Integration**: Local AI for job analysis
- **PostgreSQL Database**: Persistent data storage
- **Redis**: Caching and session management
- **APScheduler**: Automated task scheduling
- **Notification Service**: Multi-platform push notifications

### Files Created (20+ files)
```
job-crawler/
├── Docker & Config (5 files)
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── start.sh
│
├── Documentation (4 files)
│   ├── README.md (comprehensive guide)
│   ├── SETUP.md (quick start)
│   ├── ARCHITECTURE.md (technical details)
│   └── (this file)
│
├── Application Code (11 files)
│   ├── main.py
│   ├── app/config.py
│   ├── app/database.py
│   ├── app/models.py
│   ├── app/api.py
│   ├── app/crawler/linkedin_crawler.py
│   ├── app/crawler/indeed_crawler.py
│   ├── app/crawler/orchestrator.py
│   ├── app/ai/analyzer.py
│   ├── app/notifications/notifier.py
│   └── app/utils/crypto.py
│
├── Frontend (React TypeScript)
│   ├── src/components/ - Reusable UI components
│   ├── src/pages/ - Page components (Dashboard, Jobs, Companies, etc.)
│   ├── src/services/ - API service layer
│   └── src/types/ - TypeScript definitions
└── static/ - Built frontend assets (compiled from frontend/)
```

## 🚀 Quick Start (10 Minutes)

1. **Setup**
   ```bash
   cd job-crawler
   cp .env.example .env
   # Edit .env with your notification settings
   ```

2. **Start**
   ```bash
   ./start.sh
   ```

3. **Configure**
   - Open http://localhost:8001/static/index.html
   - Add LinkedIn credentials in Settings
   - Create your first search

4. **Test**
   - Click "Run Search Now"
   - Check your phone for notification
   - View results in dashboard

## 🎯 Key Features

### 1. Smart Job Matching
- AI analyzes each job against your criteria
- Match scores (0-100%)
- Pros/cons extraction
- Keyword matching

### 2. Flexible Search
- Multiple concurrent searches
- Platform selection (LinkedIn, Indeed, or both)
- Location filtering
- Remote-only option
- Job type and experience level filters

### 3. Application Tracking
- Status management (new, viewed, applied, rejected, saved)
- Follow-up reminders
- Personal notes
- Application history

### 4. Notifications
Choose your preferred method:
- **ntfy.sh**: Free, open-source, privacy-focused
- **Pushover**: Reliable, feature-rich
- **Telegram**: Familiar messaging platform

## 🔧 Customization Options

### Change Crawl Frequency
Edit `.env`:
```env
CRAWL_INTERVAL_MINUTES=15  # Every 15 minutes
```

### Use Different AI Model
```bash
# In .env
OLLAMA_MODEL=mistral

# Download model
docker exec job-crawler-ollama ollama pull mistral
```

### Add Custom Platforms
Extend `app/crawler/` with new crawler classes.
Follow the pattern in `linkedin_crawler.py`.

### Customize Dashboard
Edit `static/index.html` to match your preferences.

## 📊 System Requirements

**Minimum:**
- 2GB RAM
- 10GB disk space
- Docker & Docker Compose

**Recommended:**
- 4GB RAM
- 20GB disk space
- SSD storage

**Network:**
- Internet connection for job platforms
- No incoming ports needed (unless accessing remotely)

## 🔐 Security Notes

- **Credentials**: Encrypted with Fernet (AES-128)
- **Data**: Stored locally, never sent to third parties
- **AI**: 100% local processing with Ollama
- **Notifications**: Encrypted in transit (HTTPS)
- **API**: Can add authentication if exposing publicly

## 🎓 Learning Opportunities

This project demonstrates:
- **Web Scraping**: Selenium automation
- **API Design**: RESTful endpoints with FastAPI
- **Database Design**: SQLAlchemy ORM
- **AI Integration**: Local LLM usage
- **Containerization**: Multi-service Docker setup
- **Task Scheduling**: Background job processing
- **Real-time Notifications**: Push notification services

## 🐛 Troubleshooting

### Common Issues

**Jobs not found:**
- Check credentials
- Verify LinkedIn isn't showing captcha
- Try broader keywords

**Notifications not working:**
- Test with manual trigger
- Verify topic/token in .env
- Check phone app

**Slow performance:**
- First Ollama run downloads 4GB
- Consider lighter model (mistral)
- Check Docker resources

**Selenium errors:**
- Restart chrome: `docker-compose restart selenium-chrome`
- Check logs: `docker-compose logs selenium-chrome`

### Get Logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs job-crawler
docker-compose logs ollama
docker-compose logs selenium-chrome

# Follow live
docker-compose logs -f job-crawler
```

## 📈 Next Steps

### Immediate (Today)
1. Set up notification method
2. Add your credentials
3. Create 2-3 searches
4. Run first search
5. Verify notifications work

### Short-term (This Week)
1. Refine search criteria based on results
2. Set up follow-up reminders
3. Track your applications
4. Adjust AI model if needed

### Long-term (This Month)
1. Monitor match score accuracy
2. Add more platforms (if needed)
3. Customize dashboard styling
4. Set up remote access (optional)
5. Fine-tune notification preferences

## 🌟 Advanced Features

### Remote Access
To access from anywhere:
1. Set up reverse proxy (nginx/Caddy)
2. Use Tailscale or Cloudflare Tunnel
3. Add authentication to API

### Analytics
Add to the system:
- Job market trends
- Company insights
- Salary analysis
- Response rate tracking

### Integrations
Potential additions:
- Google Calendar for interviews
- Gmail for application emails
- Notion/Airtable for tracking
- Slack notifications

### AI Enhancements
- Resume matching
- Cover letter generation
- Interview prep suggestions
- Salary negotiation tips

## 💡 Pro Tips

1. **Start Narrow**: Begin with specific, targeted searches
2. **Check Daily**: Review new jobs each morning
3. **Update Status**: Mark jobs as you review them
4. **Use Notes**: Add thoughts for each job
5. **Set Reminders**: Follow up on applications
6. **Adjust Criteria**: Refine based on results
7. **Monitor Scores**: Trust high-match jobs
8. **Stay Organized**: Use the status system

## 🤝 Contributing

Want to improve this system?
- Add new job platforms
- Improve AI analysis prompts
- Enhance UI/UX
- Add new notification methods
- Optimize performance
- Write better documentation

## 📞 Support

**Check First:**
1. README.md - Full documentation
2. SETUP.md - Quick start guide
3. ARCHITECTURE.md - Technical details
4. Docker logs - Error messages

**Common Resources:**
- Ollama docs: https://ollama.ai
- FastAPI docs: https://fastapi.tiangolo.com
- Selenium docs: https://selenium.dev
- ntfy docs: https://ntfy.sh

## ✨ Final Notes

This is a **complete, production-ready system** that:
- Runs 24/7 automatically
- Requires minimal maintenance
- Scales with your needs
- Respects your privacy
- Costs nothing to run (except electricity)

The only things you need to provide:
1. Your job search preferences
2. Platform credentials
3. Notification preferences

Everything else is handled automatically!

## 🎊 Success Criteria

You'll know it's working when:
- ✅ Dashboard shows statistics
- ✅ Jobs appear after searches
- ✅ Notifications arrive on phone
- ✅ AI match scores are reasonable
- ✅ You can track applications
- ✅ Follow-ups are scheduled

## 🚀 Ready to Start?

```bash
cd job-crawler
./start.sh
```

Then open: http://localhost:8001/static/index.html

**Good luck with your job search! 🎯**

---

**Questions?** Check the README.md for detailed information.
**Issues?** Review the logs with `docker-compose logs`.
**Success?** Update your resume and start applying! 💼

---

**Status**: 🟢 Production Ready - All Features Complete
**Last Updated**: November 5, 2025
**Current Deployment**: pi-forge (192.168.50.157:8001)
**All Phases**: ✅ Complete - System fully operational
