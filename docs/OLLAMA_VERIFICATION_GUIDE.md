# Ollama Verification and Document Generation Guide

This guide covers the new Ollama verification utilities and AI-powered document generation features for creating tailored resumes and cover letters.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Ollama Verification](#ollama-verification)
- [Document Generation](#document-generation)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Overview

The job crawler now includes enhanced AI capabilities:

1. **Ollama Verification** - Comprehensive health checks for Ollama setup
2. **Resume Generation** - AI-powered tailored resumes for specific jobs
3. **Cover Letter Generation** - Custom cover letters matching job requirements
4. **Automated Testing** - Complete test suite for AI functionality

## Quick Start

### 1. Verify Ollama Setup

Before using AI features, verify your Ollama installation:

```bash
# Quick health check
python verify_ollama.py --quick

# Full verification with detailed report
python verify_ollama.py

# Run complete test suite
python verify_ollama.py --test
```

### 2. Expected Output

A healthy Ollama setup will show:

```
======================================================================
OLLAMA VERIFICATION REPORT
======================================================================
Timestamp: 2025-11-04T10:30:00.000000
Host: http://ollama:11434
Model: llama2
Overall Status: HEALTHY
Production Ready: YES

DETAILED CHECKS:
----------------------------------------------------------------------

✓ Server Accessible
  Status: PASS
  Message: Ollama server is accessible
  response_time_ms: 45.2

✓ Api Responding
  Status: PASS
  Message: API is responding correctly
  available_models_count: 3

✓ Model Available
  Status: PASS
  Message: Model "llama2" is available

✓ Generation Works
  Status: PASS
  Message: Text generation works
  generation_time_seconds: 2.35

✓ Json Parsing Works
  Status: PASS
  Message: JSON generation and parsing works
======================================================================
```

## Ollama Verification

### Using the OllamaVerifier Class

```python
from app.ai import OllamaVerifier, verify_ollama_setup

# Method 1: Quick check
verifier = OllamaVerifier()
is_healthy = await verifier.quick_check()
if is_healthy:
    print("Ollama is ready!")

# Method 2: Detailed verification
results = await verify_ollama_setup()
print(f"Status: {results['overall_status']}")
print(f"Production ready: {results['ready_for_production']}")

# Method 3: Full report
verifier = OllamaVerifier()
results = await verifier.verify_connection()
report = verifier.format_report(results)
print(report)
```

### What Gets Verified

The verification checks:

1. **Server Accessibility** - Can we connect to Ollama?
2. **API Response** - Is the API responding correctly?
3. **Model Availability** - Is the configured model installed?
4. **Text Generation** - Can we generate text?
5. **JSON Parsing** - Can we generate and parse structured responses?

### Configuration

Set these environment variables:

```bash
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama2
```

Or update `app/config.py`:

```python
class Settings(BaseSettings):
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama2"
```

## Document Generation

### Overview

The `DocumentGenerator` class creates tailored resumes and cover letters using AI analysis of job postings and user profiles.

### Setup User Profile

First, create a user profile with your information:

```python
from app.models import UserProfile
from app.database import SessionLocal

# Create user profile
profile = UserProfile(
    skills=[
        "Python", "FastAPI", "PostgreSQL", "Docker",
        "AWS", "Machine Learning", "RESTful APIs"
    ],
    experience=[
        {
            "title": "Senior Software Engineer",
            "company": "Tech Company",
            "duration": "2020-2023",
            "description": "Developed backend services using Python and FastAPI"
        }
    ],
    education=[
        {
            "degree": "Bachelor of Science in Computer Science",
            "institution": "University Name",
            "year": "2018"
        }
    ],
    base_resume="""
        Experienced software engineer with 5+ years of Python development.
        Specialized in backend services, API development, and cloud infrastructure.
        Strong background in AI/ML integration and scalable system design.
    """
)

db = SessionLocal()
db.add(profile)
db.commit()
```

### Generate Documents for a Job

```python
from app.ai import DocumentGenerator
from app.models import Job, UserProfile
from app.database import SessionLocal

async def generate_documents_for_job(job_id: int):
    db = SessionLocal()
    generator = DocumentGenerator()

    # Get job and user profile
    job = db.query(Job).filter(Job.id == job_id).first()
    profile = db.query(UserProfile).first()

    # Generate both resume and cover letter
    results = await generator.generate_both(job, profile, db)

    if results['resume']:
        print(f"Resume generated: {results['resume'].id}")

    if results['cover_letter']:
        print(f"Cover letter generated: {results['cover_letter'].id}")

    db.close()
```

### Generate for Top Jobs

Automatically generate documents for your top-matched jobs:

```python
from app.ai import DocumentGenerator
from app.database import SessionLocal

async def generate_for_top_jobs():
    db = SessionLocal()
    generator = DocumentGenerator()

    # Generate for top 5 jobs
    results = await generator.generate_for_top_jobs(db, limit=5)

    for result in results:
        print(f"Job: {result['job_title']} at {result['company']}")
        print(f"Match Score: {result['match_score']}")
        print(f"Resume: {'Generated' if result.get('resume_generated') else 'Exists'}")
        print(f"Cover Letter: {'Generated' if result.get('cover_letter_generated') else 'Exists'}")
        print("---")

    db.close()
```

### Scheduled Generation

Set up automatic document generation in `main.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.ai import DocumentGenerator

scheduler = AsyncIOScheduler()

async def scheduled_document_generation():
    """Generate documents for top jobs daily at 3 PM"""
    db = SessionLocal()
    generator = DocumentGenerator()

    results = await generator.generate_for_top_jobs(db, limit=5)
    logger.info(f"Generated documents for {len(results)} jobs")

    db.close()

# Schedule for 3 PM daily
scheduler.add_job(
    scheduled_document_generation,
    'cron',
    hour=15,
    minute=0,
    id='daily_document_generation'
)
```

### Document Storage

Generated documents are saved in two places:

1. **Database** - Full content stored in `generated_documents` table
2. **Files** - Optional file storage in:
   - Resumes: `RESUME_STORAGE_PATH` (default: `/app/data/resumes`)
   - Cover Letters: `COVER_LETTER_STORAGE_PATH` (default: `/app/data/cover_letters`)

File naming format: `{CompanyName}_{JobID}_{Timestamp}.txt`

### Retrieve Generated Documents

```python
from app.models import GeneratedDocument
from sqlalchemy import select

async def get_documents_for_job(job_id: int, db: AsyncSession):
    result = await db.execute(
        select(GeneratedDocument)
        .where(GeneratedDocument.job_id == job_id)
    )
    documents = result.scalars().all()

    for doc in documents:
        print(f"Type: {doc.document_type}")
        print(f"Generated: {doc.generated_at}")
        print(f"Content: {doc.content[:200]}...")
        print(f"File: {doc.file_path}")
```

## Testing

### Run All Tests

```bash
# Using pytest
pytest tests/test_ollama_integration.py -v

# Direct execution
python tests/test_ollama_integration.py

# Using verification script
python verify_ollama.py --test
```

### Test Coverage

The test suite includes:

1. **Verification Tests**
   - Server accessibility
   - API response
   - Model availability
   - Text generation
   - JSON generation

2. **Analyzer Tests**
   - Job analysis
   - Company profile analysis
   - Match score calculation

3. **Document Generator Tests**
   - Resume prompt building
   - Cover letter prompt building
   - Direct Ollama calls
   - Document generation

4. **Integration Tests**
   - End-to-end verification
   - Complete workflow tests

### Run Specific Test Classes

```bash
# Only verification tests
pytest tests/test_ollama_integration.py::TestOllamaVerification -v

# Only analyzer tests
pytest tests/test_ollama_integration.py::TestJobAnalyzer -v

# Only document generator tests
pytest tests/test_ollama_integration.py::TestDocumentGenerator -v
```

## Troubleshooting

### Ollama Not Accessible

**Error**: `Cannot connect to Ollama server`

**Solutions**:
1. Check if Ollama is running:
   ```bash
   docker ps | grep ollama
   ```

2. Verify the host URL in `.env`:
   ```bash
   OLLAMA_HOST=http://ollama:11434
   ```

3. Test connection directly:
   ```bash
   curl http://ollama:11434/api/tags
   ```

### Model Not Available

**Error**: `Model "llama2" is not available`

**Solutions**:
1. Pull the model:
   ```bash
   docker exec -it ollama ollama pull llama2
   ```

2. List available models:
   ```bash
   docker exec -it ollama ollama list
   ```

3. Update model in `.env`:
   ```bash
   OLLAMA_MODEL=your-model-name
   ```

### Generation Timeout

**Error**: `Timeout waiting for Ollama response`

**Solutions**:
1. Increase timeout in code:
   ```python
   async with httpx.AsyncClient(timeout=120.0) as client:
   ```

2. Use a faster/smaller model:
   ```bash
   OLLAMA_MODEL=llama2:7b  # Faster than larger models
   ```

3. Check system resources:
   ```bash
   docker stats ollama
   ```

### Poor Quality Output

**Issue**: Generated content is not relevant or poorly formatted

**Solutions**:
1. Adjust temperature (0.1-1.0):
   ```python
   "options": {
       "temperature": 0.7,  # Lower = more focused, Higher = more creative
   }
   ```

2. Increase max tokens:
   ```python
   "num_predict": 2000,  # More tokens for longer output
   ```

3. Improve prompts in `document_generator.py`

4. Try a more capable model:
   ```bash
   docker exec -it ollama ollama pull llama2:13b
   OLLAMA_MODEL=llama2:13b
   ```

### No User Profile Found

**Error**: `No user profile found. Cannot generate documents.`

**Solution**: Create a user profile:

```python
from app.models import UserProfile
from app.database import SessionLocal

db = SessionLocal()
profile = UserProfile(
    skills=["Python", "FastAPI"],
    experience=[{"title": "Developer", "company": "Company"}],
    education=[{"degree": "BS Computer Science"}],
    base_resume="Your base resume content..."
)
db.add(profile)
db.commit()
db.close()
```

## API Integration

### Add API Endpoints

Create endpoints for document generation in `app/api.py`:

```python
from app.ai import DocumentGenerator
from app.models import Job, UserProfile, GeneratedDocument

@app.post("/api/jobs/{job_id}/generate-documents")
async def generate_documents(job_id: int, db: AsyncSession = Depends(get_db)):
    """Generate resume and cover letter for a job"""
    generator = DocumentGenerator()

    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="User profile not found")

    results = await generator.generate_both(job, profile, db)

    return {
        "job_id": job_id,
        "resume_id": results['resume'].id if results['resume'] else None,
        "cover_letter_id": results['cover_letter'].id if results['cover_letter'] else None
    }

@app.get("/api/documents/{document_id}")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Get a generated document"""
    doc = await db.get(GeneratedDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": doc.id,
        "job_id": doc.job_id,
        "type": doc.document_type,
        "content": doc.content,
        "generated_at": doc.generated_at,
        "file_path": doc.file_path
    }
```

## Best Practices

1. **Verify Before Use** - Always run verification before production use
2. **Monitor Performance** - Track generation times and quality
3. **Update Profiles** - Keep user profiles current
4. **Review Output** - Always review generated documents before use
5. **Adjust Prompts** - Customize prompts for your needs
6. **Use Appropriate Models** - Balance speed vs quality
7. **Handle Errors** - Implement proper error handling and fallbacks
8. **Test Regularly** - Run tests after updates or configuration changes

## Next Steps

1. Customize prompts in `document_generator.py` for your needs
2. Add more user profile fields for better personalization
3. Implement document versioning
4. Add support for different document formats (PDF, DOCX)
5. Create UI for managing generated documents
6. Add feedback mechanism to improve quality

## Support

For issues or questions:
- Check the troubleshooting section above
- Review Ollama documentation: https://ollama.ai/
- Check project issues on GitHub
