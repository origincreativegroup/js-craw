"""AI-powered resume and cover letter generator using Ollama"""
import logging
import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import httpx

from app.config import settings
from app.models import Job, UserProfile, GeneratedDocument
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Generate tailored resumes and cover letters using Ollama"""

    def __init__(self):
        self.ollama_url = f"{settings.OLLAMA_HOST}/api/generate"
        self.model = settings.OLLAMA_MODEL
        self.resume_path = Path(settings.RESUME_STORAGE_PATH)
        self.cover_letter_path = Path(settings.COVER_LETTER_STORAGE_PATH)
        self._enabled = getattr(settings, "OLLAMA_ENABLED", True)
    
    def _is_enabled(self) -> bool:
        return getattr(settings, "OLLAMA_ENABLED", self._enabled)

        # Ensure directories exist
        self.resume_path.mkdir(parents=True, exist_ok=True)
        self.cover_letter_path.mkdir(parents=True, exist_ok=True)

    async def generate_resume(
        self,
        job: Job,
        user_profile: UserProfile,
        db: AsyncSession
    ) -> Optional[GeneratedDocument]:
        """
        Generate a tailored resume for a specific job posting.

        Args:
            job: The job posting to tailor the resume for
            user_profile: User's profile with base resume and experience
            db: Database session

        Returns:
            GeneratedDocument object with generated resume
        """
        if not self._is_enabled():
            logger.info("Ollama integration disabled; skipping resume generation")
            return None

        try:
            logger.info(f"Generating resume for job {job.id}: {job.title} at {job.company}")

            # Build the prompt
            prompt = self._build_resume_prompt(job, user_profile)

            # Generate content
            resume_content = await self._call_ollama(prompt, max_tokens=2000)

            if not resume_content:
                logger.error("Failed to generate resume content")
                return None

            # Save to database
            doc = GeneratedDocument(
                job_id=job.id,
                document_type="resume",
                content=resume_content,
                generated_at=datetime.utcnow()
            )

            # Optionally save to file
            if settings.RESUME_STORAGE_PATH:
                file_path = await self._save_to_file(
                    content=resume_content,
                    job=job,
                    doc_type="resume"
                )
                doc.file_path = file_path

            db.add(doc)
            await db.commit()
            await db.refresh(doc)

            logger.info(f"Resume generated successfully for job {job.id}")
            return doc

        except Exception as e:
            logger.error(f"Error generating resume: {e}", exc_info=True)
            await db.rollback()
            return None

    async def generate_cover_letter(
        self,
        job: Job,
        user_profile: UserProfile,
        db: AsyncSession
    ) -> Optional[GeneratedDocument]:
        """
        Generate a tailored cover letter for a specific job posting.

        Args:
            job: The job posting to write the cover letter for
            user_profile: User's profile with experience and skills
            db: Database session

        Returns:
            GeneratedDocument object with generated cover letter
        """
        if not self._is_enabled():
            logger.info("Ollama integration disabled; skipping cover letter generation")
            return None

        try:
            logger.info(f"Generating cover letter for job {job.id}: {job.title} at {job.company}")

            # Build the prompt
            prompt = self._build_cover_letter_prompt(job, user_profile)

            # Generate content
            cover_letter_content = await self._call_ollama(prompt, max_tokens=1500)

            if not cover_letter_content:
                logger.error("Failed to generate cover letter content")
                return None

            # Save to database
            doc = GeneratedDocument(
                job_id=job.id,
                document_type="cover_letter",
                content=cover_letter_content,
                generated_at=datetime.utcnow()
            )

            # Optionally save to file
            if settings.COVER_LETTER_STORAGE_PATH:
                file_path = await self._save_to_file(
                    content=cover_letter_content,
                    job=job,
                    doc_type="cover_letter"
                )
                doc.file_path = file_path

            db.add(doc)
            await db.commit()
            await db.refresh(doc)

            logger.info(f"Cover letter generated successfully for job {job.id}")
            return doc

        except Exception as e:
            logger.error(f"Error generating cover letter: {e}", exc_info=True)
            await db.rollback()
            return None

    async def generate_both(
        self,
        job: Job,
        user_profile: UserProfile,
        db: AsyncSession
    ) -> Dict[str, Optional[GeneratedDocument]]:
        """
        Generate both resume and cover letter for a job.

        Returns:
            Dictionary with 'resume' and 'cover_letter' keys
        """
        if not self._is_enabled():
            logger.info("Ollama integration disabled; skipping combined document generation")
            return {'resume': None, 'cover_letter': None}
        results = {
            'resume': await self.generate_resume(job, user_profile, db),
            'cover_letter': await self.generate_cover_letter(job, user_profile, db)
        }

        return results

    async def generate_for_top_jobs(
        self,
        db: AsyncSession,
        limit: int = 5
    ) -> List[Dict]:
        """
        Generate resumes and cover letters for top-ranked jobs.

        Args:
            db: Database session
            limit: Number of top jobs to process

        Returns:
            List of generation results
        """
        if not self._is_enabled():
            logger.info("Ollama integration disabled; skipping top job document generation")
            return []
        try:
            # Get user profile
            result = await db.execute(select(UserProfile).limit(1))
            user_profile = result.scalar_one_or_none()

            if not user_profile:
                logger.warning("No user profile found. Cannot generate documents.")
                return []

            # Get top jobs (highest AI match score)
            result = await db.execute(
                select(Job)
                .where(Job.ai_match_score.isnot(None))
                .order_by(Job.ai_match_score.desc())
                .limit(limit)
            )
            top_jobs = result.scalars().all()

            if not top_jobs:
                logger.info("No jobs with AI scores found")
                return []

            results = []
            for job in top_jobs:
                logger.info(f"Processing job: {job.title} at {job.company}")

                # Check if documents already exist
                existing = await db.execute(
                    select(GeneratedDocument)
                    .where(GeneratedDocument.job_id == job.id)
                )
                existing_docs = {doc.document_type: doc for doc in existing.scalars().all()}

                job_results = {
                    'job_id': job.id,
                    'job_title': job.title,
                    'company': job.company,
                    'match_score': job.ai_match_score
                }

                # Generate resume if not exists
                if 'resume' not in existing_docs:
                    resume = await self.generate_resume(job, user_profile, db)
                    job_results['resume_generated'] = resume is not None
                else:
                    job_results['resume_generated'] = False
                    job_results['resume_exists'] = True

                # Generate cover letter if not exists
                if 'cover_letter' not in existing_docs:
                    cover_letter = await self.generate_cover_letter(job, user_profile, db)
                    job_results['cover_letter_generated'] = cover_letter is not None
                else:
                    job_results['cover_letter_generated'] = False
                    job_results['cover_letter_exists'] = True

                results.append(job_results)

            return results

        except Exception as e:
            logger.error(f"Error generating documents for top jobs: {e}", exc_info=True)
            return []

    def _build_resume_prompt(self, job: Job, user_profile: UserProfile) -> str:
        """Build prompt for resume generation"""

        skills = user_profile.skills or []
        experience = user_profile.experience or []
        education = user_profile.education or []
        base_resume = user_profile.base_resume or ""

        # Extract key requirements from job description
        job_keywords = []
        if job.description:
            # Look for common requirement patterns
            desc_lower = job.description.lower()
            common_tech = ['python', 'javascript', 'react', 'node', 'sql', 'aws', 'docker', 'kubernetes', 'git', 'linux']
            for tech in common_tech:
                if tech in desc_lower:
                    job_keywords.append(tech)
        
        # Extract years of experience if mentioned
        experience_years = None
        if job.description:
            import re
            exp_match = re.search(r'(\d+)\+?\s*(years?|yrs?)\s*(of\s*)?(experience|exp)', job.description, re.IGNORECASE)
            if exp_match:
                experience_years = exp_match.group(1)

        prompt = f"""You are an expert resume writer specializing in ATS-optimized resumes. Create a tailored, professional resume for this specific job application.

═══════════════════════════════════════════════════════════════
JOB TARGET
═══════════════════════════════════════════════════════════════
Position: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}
Key Requirements: {', '.join(job_keywords[:10]) if job_keywords else 'See full description'}
Experience Required: {f"{experience_years}+ years" if experience_years else "See description"}

Job Description (excerpt):
{job.description[:2500] if job.description else 'Not available'}
{'...' if job.description and len(job.description) > 2500 else ''}

═══════════════════════════════════════════════════════════════
CANDIDATE PROFILE
═══════════════════════════════════════════════════════════════
Skills: {', '.join(skills) if skills else 'General professional skills'}

Education:
{json.dumps(education, indent=2) if education else 'To be specified'}

Work Experience:
{json.dumps(experience, indent=2) if experience else 'To be specified'}

Base Resume (reference):
{base_resume[:1500] if base_resume else 'Create a professional resume structure'}

═══════════════════════════════════════════════════════════════
RESUME GENERATION REQUIREMENTS
═══════════════════════════════════════════════════════════════
1. TARGETED TAILORING:
   - Match keywords from the job description naturally throughout the resume
   - Prioritize experiences and skills most relevant to {job.title} at {job.company}
   - Use industry-specific terminology from the job posting

2. ATS OPTIMIZATION:
   - Use standard section headers: Professional Summary, Skills, Experience, Education
   - Include relevant keywords from the job description
   - Use clean, parseable formatting
   - Avoid graphics, tables, or complex formatting

3. CONTENT QUALITY:
   - Start each bullet point with strong action verbs (Led, Developed, Implemented, etc.)
   - Include quantifiable achievements (numbers, percentages, scale)
   - Show progression and impact in each role
   - Keep professional summary to 3-4 lines highlighting top qualifications

4. STRUCTURE:
   - Professional Summary (3-4 lines)
   - Core Skills/Technical Skills section (relevant to job)
   - Professional Experience (reverse chronological, most relevant first)
   - Education
   - Optional: Certifications, Projects (if highly relevant)

5. LENGTH:
   - Target 1-2 pages of content
   - Be concise but comprehensive
   - Every line should add value and relevance

6. FORMATTING:
   - Use clear section headers
   - Consistent date formatting (MM/YYYY - MM/YYYY)
   - Clean, professional presentation
   - Use markdown for formatting if needed

Generate a professional, ATS-optimized resume tailored specifically for the {job.title} position at {job.company}:"""

        return prompt

    def _build_cover_letter_prompt(self, job: Job, user_profile: UserProfile) -> str:
        """Build prompt for cover letter generation"""

        skills = user_profile.skills or []
        experience = user_profile.experience or []

        # Extract key highlights from experience
        experience_highlights = []
        achievements = []
        for exp in experience[:3]:  # Top 3 experiences
            if isinstance(exp, dict):
                title = exp.get('title', '')
                company = exp.get('company', '')
                description = exp.get('description', '')
                if title and company:
                    experience_highlights.append(f"{title} at {company}")
                if description:
                    achievements.append(description[:200])

        # Extract company name for personalization
        company_name = job.company
        recruiter_greeting = f"Dear Hiring Manager"  # Could be enhanced with name detection

        prompt = f"""You are an expert career coach and cover letter writer. Create a compelling, personalized cover letter that stands out.

═══════════════════════════════════════════════════════════════
JOB TARGET
═══════════════════════════════════════════════════════════════
Position: {job.title}
Company: {company_name}
Location: {job.location or 'Not specified'}

Job Description:
{job.description[:2500] if job.description else 'Not available'}
{'...' if job.description and len(job.description) > 2500 else ''}

═══════════════════════════════════════════════════════════════
CANDIDATE BACKGROUND
═══════════════════════════════════════════════════════════════
Key Skills: {', '.join(skills[:15]) if skills else 'Professional skills'}
Relevant Experience: {', '.join(experience_highlights) if experience_highlights else 'Professional experience'}
Key Achievements: {'; '.join(achievements[:3]) if achievements else 'See experience'}

═══════════════════════════════════════════════════════════════
COVER LETTER REQUIREMENTS
═══════════════════════════════════════════════════════════════
1. OPENING (First Paragraph):
   - Start with enthusiasm and specific mention of the {job.title} position
   - Reference where you learned about the opportunity (if applicable)
   - State why you're excited about this specific role at {company_name}
   - Make it memorable and personal, not generic

2. BODY (2-3 Paragraphs):
   - Paragraph 1: Highlight 2-3 most relevant qualifications
     * Match specific requirements from the job description
     * Use concrete examples from experience
     * Show how your background aligns with their needs
   
   - Paragraph 2: Demonstrate value and fit
     * Share a specific achievement or project that relates to the role
     * Show understanding of the company/role challenges
     * Connect your experience to what they're looking for
   
   - Optional Paragraph 3: Cultural fit and motivation
     * Why you're interested in {company_name} specifically
     * What you can contribute to their team
     * Long-term alignment with company goals

3. CLOSING (Final Paragraph):
   - Reiterate enthusiasm for the position
   - Express confidence in being a strong fit
   - Professional call to action
   - Thank them for consideration

4. TONE & STYLE:
   - Professional yet personable and authentic
   - Confident but not arrogant
   - Enthusiastic but not overly casual
   - Specific to this role, not generic
   - Show personality while remaining professional

5. LENGTH:
   - Target: 250-400 words (3-4 paragraphs)
   - Be concise but comprehensive
   - Every sentence should add value

6. FORMATTING:
   - Professional business letter format
   - Include date, greeting, body, closing, signature line
   - Clean, readable formatting
   - Use proper paragraph breaks

7. PERSONALIZATION:
   - Reference specific aspects of the job description
   - Mention company name naturally (not overused)
   - Show you've researched and understand the role
   - Connect your experience to their specific needs

Generate a compelling, personalized cover letter for the {job.title} position at {company_name}:"""

        return prompt

    async def _call_ollama(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call Ollama API for text generation"""
        if not self._is_enabled():
            raise RuntimeError("Ollama integration disabled via settings")
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,  # More creative for document generation
                            "num_predict": max_tokens,
                            "top_p": 0.9
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '').strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return ""

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return ""

    async def _save_to_file(
        self,
        content: str,
        job: Job,
        doc_type: str
    ) -> Optional[str]:
        """Save generated document to file"""
        try:
            # Create filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            company_safe = "".join(c for c in job.company if c.isalnum() or c in (' ', '-', '_')).strip()
            company_safe = company_safe.replace(' ', '_')[:50]
            filename = f"{company_safe}_{job.id}_{timestamp}.txt"

            # Determine path
            if doc_type == "resume":
                file_path = self.resume_path / filename
            else:
                file_path = self.cover_letter_path / filename

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Saved {doc_type} to {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error saving document to file: {e}")
            return None
