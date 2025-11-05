"""Generate tailored resumes and cover letters without storing them to a job"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TailoredApplicationBuilder:
    """Create resumes and cover letters from arbitrary job details"""

    def __init__(self):
        self.ollama_url = f"{settings.OLLAMA_HOST}/api/generate"
        self.model = settings.OLLAMA_MODEL

    async def generate_documents(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: Optional[str],
        user_summary: Optional[str],
        user_skills: List[str],
        portfolio_content: str,
        document_types: List[str],
    ) -> Dict[str, Optional[str]]:
        results: Dict[str, Optional[str]] = {doc_type: None for doc_type in document_types}

        if "resume" in document_types:
            resume_prompt = self._build_resume_prompt(
                job_title,
                company,
                job_description,
                requirements,
                user_summary,
                user_skills,
                portfolio_content,
            )
            results["resume"] = await self._call_ollama(resume_prompt, max_tokens=2000)

        if "cover_letter" in document_types:
            cover_prompt = self._build_cover_letter_prompt(
                job_title,
                company,
                job_description,
                requirements,
                user_summary,
                user_skills,
                portfolio_content,
            )
            results["cover_letter"] = await self._call_ollama(cover_prompt, max_tokens=1000)

        return results

    def _build_resume_prompt(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: Optional[str],
        user_summary: Optional[str],
        user_skills: List[str],
        portfolio_content: str,
    ) -> str:
        return f"""
You are an executive resume writer. Craft a resume tailored for the role below using the candidate materials.

ROLE:
- Title: {job_title}
- Company: {company}
- Description:
{job_description[:4000]}

REQUIREMENTS:
{requirements or '(not provided)'}

CANDIDATE SNAPSHOT:
- Summary: {user_summary or '(not provided)'}
- Core skills: {', '.join(user_skills) if user_skills else '(not provided)'}

PORTFOLIO MATERIAL (markdown snippets from resumes, project narratives, etc.):
{portfolio_content[:8000]}

Create a polished, ATS-friendly resume in markdown with sections for Summary, Core Skills, Experience, Projects (if relevant), and Education. Highlight quantifiable achievements pulled from the portfolio. Limit the output to around 650 words.
"""

    def _build_cover_letter_prompt(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: Optional[str],
        user_summary: Optional[str],
        user_skills: List[str],
        portfolio_content: str,
    ) -> str:
        return f"""
You are a persuasive career storyteller. Draft a cover letter tailored to this role.

ROLE:
- Title: {job_title}
- Company: {company}
- Key points from description:
{job_description[:2000]}

REQUIREMENTS:
{requirements or '(not provided)'}

CANDIDATE SUMMARY:
{user_summary or '(not provided)'}

KEY SKILLS TO EMPHASIZE: {', '.join(user_skills) if user_skills else '(not provided)'}

PORTFOLIO MATERIAL:
{portfolio_content[:4000]}

Write a 3-4 paragraph cover letter (~300 words) that quickly connects the candidate's accomplishments to the company's needs. Keep the tone enthusiastic but professional and close with a confident call to action.
"""

    async def _call_ollama(self, prompt: str, max_tokens: int) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.6,
                            "num_predict": max_tokens,
                            "top_p": 0.9,
                        },
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return payload.get("response", "").strip()
        except Exception as exc:  # pragma: no cover - network failures
            logger.error("Failed to generate tailored document: %s", exc, exc_info=True)
            return None
