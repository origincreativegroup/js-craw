# OpenWebUI Integration

OpenWebUI provides a beautiful, user-friendly chat interface for interacting with Ollama models. This integration enhances the job search system with AI-powered chat capabilities.

## Overview

This system is designed to work with your existing OpenWebUI instance. Make sure your OpenWebUI is configured to use the same Ollama instance as the job crawler.

OpenWebUI allows you to:

- **Chat with AI** about your job searches
- **Get personalized advice** on job applications
- **Analyze job descriptions** with AI assistance
- **Generate resumes and cover letters** tailored to specific jobs
- **Ask questions** about companies and roles
- **Get interview preparation tips**

## Access

Use your existing OpenWebUI instance. Update the URL in configuration:

**In `.env` file:**
```env
OPENWEBUI_URL=http://your-openwebui-host:port
```

Or via API:
```bash
curl http://localhost:8001/api/openwebui
```

## Configuration

### Job Crawler Configuration

Update your `.env` file or `app/config.py`:
```python
OPENWEBUI_URL = "http://your-openwebui-host:port"  # Your existing OpenWebUI URL
```

### OpenWebUI Configuration

Make sure your existing OpenWebUI is configured to use the same Ollama instance:

- **Ollama Host**: Should match `OLLAMA_HOST` in job crawler config
- **Shared Ollama**: Both systems should point to the same Ollama instance (e.g., `http://192.168.50.248:11434`)

## Features

### 1. Job Search Assistant

Chat with the AI about your job search:

```
You: "What are the best remote software engineering jobs for Python developers?"

AI: [Provides tailored advice based on current job market]
```

### 2. Job Description Analysis

Paste a job description and get insights:

```
You: "Analyze this job description:
[Paste job description]

What skills are most important? What are potential red flags?"
```

### 3. Resume/Cover Letter Generation

Generate tailored documents:

```
You: "Generate a cover letter for a Senior Software Engineer 
position at [Company] emphasizing my Python and React experience."
```

### 4. Interview Preparation

Get interview tips:

```
You: "I have an interview for a DevOps Engineer role. 
What technical questions should I prepare for?"
```

### 5. Company Research

Ask about companies:

```
You: "Tell me about [Company Name]. What's their tech stack 
and company culture like?"
```

## Use Cases

### Scenario 1: Preparing for Applications

1. Open OpenWebUI at http://localhost:3000
2. Select a job from the dashboard
3. Copy the job description
4. In OpenWebUI, ask: "Help me prepare for this role: [paste description]"
5. Get personalized advice and talking points

### Scenario 2: Improving Your Profile

1. Chat with AI about your skills
2. Ask: "What skills should I learn to be competitive for [role type]?"
3. Get recommendations based on current job market

### Scenario 3: Cover Letter Generation

1. Select a job you're interested in
2. In OpenWebUI, provide your background and the job details
3. Ask: "Write a compelling cover letter for this position"
4. Review and customize the generated letter

## Integration with Job Crawler

### Data Flow

```
Job Crawler (Ollama)
    ↓
Analyzes jobs → Saves to database
    ↓
OpenWebUI (Ollama)
    ↓
Chat interface → Get insights about jobs
```

### API Integration

The job crawler API provides information about OpenWebUI:

```bash
GET /api/openwebui
```

Response:
```json
{
  "enabled": true,
  "url": "http://localhost:3000",
  "ollama_host": "http://192.168.50.248:11434",
  "ollama_model": "llama3.1",
  "description": "OpenWebUI provides a chat interface...",
  "features": [...]
}
```

## Custom Prompts

You can create custom prompts in OpenWebUI for common tasks:

### Prompt: Job Match Analyzer

```
You are a job search assistant. Analyze how well a job matches 
the user's profile. Consider:
- Required skills vs user's skills
- Company culture fit
- Growth opportunities
- Compensation expectations
- Work-life balance

Provide a detailed analysis with a match score (0-100).
```

### Prompt: Resume Optimizer

```
You are a resume optimization expert. Review the user's resume 
and suggest improvements for a specific job posting. Focus on:
- Keyword optimization
- Achievement quantification
- Relevance highlighting
- Format improvements
```

## Troubleshooting

### OpenWebUI Won't Start

```bash
# Check logs
docker compose logs open-webui

# Restart service
docker compose restart open-webui
```

### Can't Connect to Ollama

Verify Ollama is accessible:
```bash
# From host
curl http://192.168.50.248:11434/api/tags

# From OpenWebUI container
docker exec job-crawler-openwebui curl http://192.168.50.248:11434/api/tags
```

### Model Not Available

Make sure the model is downloaded on your Ollama server:
```bash
# On Ollama server (ai-srv)
ollama pull llama3.1
ollama pull llama2
```

## Security Notes

1. **Change WEBUI_SECRET_KEY**: Update in docker-compose.yml for production
2. **Access Control**: OpenWebUI has built-in user authentication
3. **Network**: OpenWebUI only needs access to Ollama, not job crawler database
4. **Data Privacy**: All AI processing happens locally, no data sent externally

## Advanced Configuration

### Custom Models

Add more models to `DEFAULT_MODELS`:
```yaml
- DEFAULT_MODELS=llama3.1,llama2,mistral:7b
```

### Persistence

OpenWebUI data is stored in the `open_webui_data` Docker volume:
```bash
# Backup
docker run --rm -v job-crawler_open_webui_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/openwebui-backup.tar.gz /data

# Restore
docker run --rm -v job-crawler_open_webui_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/openwebui-backup.tar.gz -C /
```

## Resources

- **OpenWebUI Docs**: https://docs.openwebui.com/
- **Ollama Docs**: https://ollama.ai/docs
- **Job Crawler API**: http://localhost:8001/docs

---

**Status**: ✅ Integrated and Ready
**Last Updated**: 2025-11-03
