from datetime import datetime, timedelta
from typing import Any, Dict, List


def _days_from_now(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).isoformat()


def build_next_steps(job: Any, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build user-clickable next-step recommendations based on job and analysis.

    Returns a list of suggestion dicts (not persisted), each containing:
      - id: stable key for UI
      - label: short label for the action
      - task_type: one of apply, research, network, prepare_interview
      - title: suggested task title
      - notes: brief notes/context
      - suggested_due_date: ISO datetime string for suggested due date
    """

    title = getattr(job, "title", "Role") or "Role"
    company = getattr(job, "company", "Company") or "Company"

    must_haves = analysis.get("must_haves") or []
    nice_to_haves = analysis.get("nice_to_haves") or []
    what_they_want = analysis.get("what_they_want") or ""
    simplified_requirements = analysis.get("simplified_requirements") or []

    suggestions: List[Dict[str, Any]] = []

    # 1) Apply now
    suggestions.append({
        "id": "apply_now",
        "label": "Apply now",
        "task_type": "apply",
        "title": f"Apply to {title} at {company}",
        "notes": ("Highlight matches to must-haves: " + ", ".join(must_haves[:3])) if must_haves else "Review description and tailor resume.",
        "suggested_due_date": _days_from_now(1),
    })

    # 2) Research company/team
    suggestions.append({
        "id": "research_company",
        "label": "Research company",
        "task_type": "research",
        "title": f"Research {company} and team for {title}",
        "notes": what_they_want or "Identify product, customers, and success metrics.",
        "suggested_due_date": _days_from_now(2),
    })

    # 3) Tailor resume
    resume_focus = must_haves[:2] or simplified_requirements[:2]
    suggestions.append({
        "id": "tailor_resume",
        "label": "Tailor resume",
        "task_type": "prepare_interview",
        "title": f"Tailor resume for {title} at {company}",
        "notes": ("Emphasize: " + ", ".join(resume_focus)) if resume_focus else "Emphasize top relevant accomplishments.",
        "suggested_due_date": _days_from_now(2),
    })

    # 4) Draft cover letter
    suggestions.append({
        "id": "draft_cover_letter",
        "label": "Draft cover letter",
        "task_type": "prepare_interview",
        "title": f"Draft cover letter for {company}",
        "notes": "Address how you meet must-haves and why this role.",
        "suggested_due_date": _days_from_now(3),
    })

    # 5) Network outreach
    suggestions.append({
        "id": "network_outreach",
        "label": "Network outreach",
        "task_type": "network",
        "title": f"Identify 1-2 contacts at {company}",
        "notes": "Find team members on LinkedIn; request a short chat.",
        "suggested_due_date": _days_from_now(3),
    })

    # 6) Schedule follow-up
    suggestions.append({
        "id": "schedule_follow_up",
        "label": "Schedule follow-up",
        "task_type": "follow_up",
        "title": f"Schedule follow-up for {title} at {company}",
        "notes": "If no response after applying, send polite follow-up.",
        "suggested_due_date": _days_from_now(7),
    })

    # 7) Optional: bridge gaps from nice-to-haves
    if nice_to_haves:
        suggestions.append({
            "id": "close_skill_gap",
            "label": "Close skill gap",
            "task_type": "research",
            "title": f"Study 1 nice-to-have for {title}",
            "notes": f"Review: {nice_to_haves[0]}",
            "suggested_due_date": _days_from_now(5),
        })

    return suggestions


