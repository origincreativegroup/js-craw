# Quick Setup Guide

## Step-by-Step Instructions

### 1. Initial Setup (5 minutes)

```bash
cd job-crawler
cp .env.example .env
nano .env  # or use your preferred editor
```

**Required changes in .env:**
- Set `SECRET_KEY` to something random
- Choose notification method (ntfy recommended)
- Set your notification credentials
 - Review HTTP/crawl tuning defaults in `docs/HTTP_CRAWL_TUNING.md` (rate limits, retries, timeouts)

### 2. Start the System

```bash
./start.sh
```

Or manually:
```bash
docker-compose up -d
docker exec job-crawler-ollama ollama pull llama2
```

### 3. Configure (2 minutes)

1. Open http://localhost:8001/static/index.html
2. Go to **Settings** tab
3. Add LinkedIn credentials
4. (Optional) Add Indeed credentials

### 4. Create First Search (1 minute)

1. Go to **Search Criteria** tab
2. Click **+ Add New Search**
3. Fill in:
   - Name: "Software Engineer"
   - Keywords: "python javascript"
   - Location: "Remote" or your city
   - Select platforms
4. Click **Create Search**

### 5. Test It!

Click **"Run Search Now"** in the header.

Within 2-3 minutes, you should:
- See jobs appear in the dashboard
- Receive a notification on your phone

## Notification Setup Details

### Option 1: ntfy.sh (Easiest)

1. Install app: https://ntfy.sh/
2. Open app, tap "+"
3. Choose any topic name: `job-alerts-john-xyz123`
4. Update .env:
   ```
   NOTIFICATION_METHOD=ntfy
   NTFY_TOPIC=job-alerts-john-xyz123
   ```

### Option 2: Pushover

1. Create account: https://pushover.net
2. Install app on phone
3. Create application in Pushover dashboard
4. Copy User Key and App Token to .env

### Option 3: Telegram

1. Message @BotFather on Telegram
2. Send `/newbot` and follow instructions
3. Get chat ID from @userinfobot
4. Update .env with bot token and chat ID

## Verification Checklist

- [ ] Docker containers running: `docker-compose ps`
- [ ] Can access dashboard: http://localhost:8001/static/index.html
- [ ] Credentials saved in Settings
- [ ] At least one search created
- [ ] Test notification received
- [ ] Jobs appear after manual search

## Common Issues

**No jobs found:**
- Verify credentials are correct
- Try broader keywords
- Check if LinkedIn requires 2FA

**No notifications:**
- Test notification manually
- Verify topic/token in .env
- Check phone app is installed

**Ollama slow:**
- First run downloads 4GB model
- Subsequent runs faster
- Consider using smaller model (mistral)

## Next Steps

1. **Refine searches** - Add more specific criteria
2. **Review jobs** - Check AI match scores
3. **Track applications** - Update job status
4. **Schedule follow-ups** - Set reminders

## Support

Check logs for errors:
```bash
docker-compose logs job-crawler
docker-compose logs selenium-chrome
docker-compose logs ollama
```

Need help? Review the full README.md
