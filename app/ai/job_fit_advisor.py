"""LLM-powered advisor that explains job requirements and evaluates fit"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class JobFitAdvisor:
    """Analyze a job description and align it with a candidate profile"""

    def __init__(self):
        self.ollama_url = f"{settings.OLLAMA_HOST}/api/generate"
        self.model = settings.OLLAMA_MODEL

    async def evaluate(
        self,
        job_title: Optional[str],
        company: Optional[str],
        job_description: str,
        requirements: Optional[str],
        user_summary: Optional[str],
        user_skills: List[str],
        user_experience: Optional[str],
        supporting_material: Optional[str] = None,
    ) -> Dict:
        prompt = self._build_prompt(
            job_title,
            company,
            job_description,
            requirements,
            user_summary,
            user_skills,
            user_experience,
            supporting_material,
        )

        try:
            response_text = await self._call_ollama(prompt)
            return self._parse_response(response_text)
        except Exception as exc:  # pragma: no cover - network failures
            logger.error("Job fit analysis failed: %s", exc, exc_info=True)
            return {
                "summary": "Unable to analyze this job right now.",
                "company_focus": None,
                "key_requirements": [],
                "skill_alignment": {
                    "overall_fit": "unknown",
                    "matched_skills": [],
                    "missing_skills": [],
                    "upskill_suggestions": [],
                },
                "tailoring_tips": [],
            }

    def _build_prompt(
        self,
        job_title: Optional[str],
        company: Optional[str],
        job_description: str,
        requirements: Optional[str],
        user_summary: Optional[str],
        user_skills: List[str],
        user_experience: Optional[str],
        supporting_material: Optional[str],
    ) -> str:
        skills = ", ".join(user_skills) if user_skills else "(skills not provided)"
        req_block = requirements or "(requirements not provided)"
        summary_block = user_summary or "(candidate summary not provided)"
        experience_block = user_experience or "(experience overview not provided)"
        support_block = supporting_material or ""

        return f"""
You are an expert career coach. Break down this job posting and explain what the company is seeking while evaluating whether the candidate is a strong fit.

Respond ONLY in JSON with the structure shown below.

JOB CONTEXT:
- Title: {job_title or 'Not specified'}
- Company: {company or 'Not specified'}
- Description:
{job_description.strip()[:4000]}

ADDITIONAL REQUIREMENTS SECTION:
{req_block}

CANDIDATE SNAPSHOT:
- Summary: {summary_block}
- Core skills: {skills}
- Experience highlights: {experience_block}

SUPPORTING MATERIAL:
{support_block[:4000]}

Return JSON using this schema:
{{
  "summary": "2-3 sentence plain-language explanation of the role",
  "company_focus": "What problems this company/team is solving and why they're hiring",
  "key_requirements": ["Concise bullet of each core requirement"],
  "skill_alignment": {{
      "overall_fit": "strong|moderate|needs_work|unknown",
      "matched_skills": ["Candidate skill that matches"],
      "missing_skills": ["Requirement not covered"],
      "upskill_suggestions": ["Specific action the candidate can take"]
  }},
  "tailoring_tips": ["How to tailor resume/cover letter"],
  "interview_prep": ["Suggested topics or questions to prepare"]
}}

Keep sentences short, actionable, and avoid filler text.
"""

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 600,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    def _parse_response(self, text: str) -> Dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                raise ValueError("No JSON object found")
            payload = json.loads(text[start:end])
            return payload
        except Exception:  # pragma: no cover - defensive
            logger.warning("Falling back to basic job fit parsing")
            return {
                "summary": text.strip()[:500] if text else "",
                "company_focus": None,
                "key_requirements": [],
                "skill_alignment": {
                    "overall_fit": "unknown",
                    "matched_skills": [],
                    "missing_skills": [],
                    "upskill_suggestions": [],
                },
                "tailoring_tips": [],
                "interview_prep": [],
            }
