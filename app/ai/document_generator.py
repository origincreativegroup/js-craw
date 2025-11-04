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

        prompt = f"""You are a professional resume writer. Create a tailored resume for the following job application.

JOB DETAILS:
- Position: {job.title}
- Company: {job.company}
- Location: {job.location or 'Not specified'}
- Job Description: {job.description[:2000] if job.description else 'Not available'}

CANDIDATE PROFILE:
Skills: {', '.join(skills) if skills else 'General skills'}
Education: {json.dumps(education) if education else 'To be specified'}

Work Experience:
{json.dumps(experience, indent=2) if experience else 'To be specified'}

Base Resume:
{base_resume[:1000] if base_resume else 'Create a professional resume structure'}

INSTRUCTIONS:
1. Tailor the resume specifically for this {job.title} position at {job.company}
2. Highlight skills and experience most relevant to the job requirements
3. Use action verbs and quantifiable achievements
4. Keep it concise (1-2 pages worth of content)
5. Format in clean, professional plain text (use markdown if needed)
6. Include relevant sections: Summary, Skills, Experience, Education
7. Emphasize how the candidate's background matches the job requirements

Generate a professional, ATS-friendly resume:"""

        return prompt

    def _build_cover_letter_prompt(self, job: Job, user_profile: UserProfile) -> str:
        """Build prompt for cover letter generation"""

        skills = user_profile.skills or []
        experience = user_profile.experience or []

        # Extract key highlights from experience
        experience_highlights = []
        for exp in experience[:3]:  # Top 3 experiences
            if isinstance(exp, dict):
                title = exp.get('title', '')
                company = exp.get('company', '')
                if title and company:
                    experience_highlights.append(f"{title} at {company}")

        prompt = f"""You are a professional career coach writing a compelling cover letter. Create a tailored cover letter for the following job application.

JOB DETAILS:
- Position: {job.title}
- Company: {job.company}
- Location: {job.location or 'Not specified'}
- Job Description: {job.description[:2000] if job.description else 'Not available'}

CANDIDATE BACKGROUND:
Key Skills: {', '.join(skills[:10]) if skills else 'Professional skills'}
Recent Experience: {', '.join(experience_highlights) if experience_highlights else 'Professional experience'}

INSTRUCTIONS:
1. Write a compelling cover letter specifically for {job.title} at {job.company}
2. Show enthusiasm for the company and role
3. Highlight 2-3 key qualifications that match the job requirements
4. Explain why the candidate is interested in this specific opportunity
5. Keep it concise (3-4 paragraphs, about 250-350 words)
6. Use a professional yet personable tone
7. Include a strong opening and closing
8. Format in clean, professional plain text

Structure:
- Opening paragraph: Express interest and mention the position
- Body paragraphs: Highlight relevant qualifications and achievements
- Closing paragraph: Express enthusiasm and call to action

Generate a professional cover letter:"""

        return prompt

    async def _call_ollama(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call Ollama API for text generation"""
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
