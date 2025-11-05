from types import SimpleNamespace

from app.ai.suggestions import build_next_steps


def test_build_next_steps_basic():
    job = SimpleNamespace(title="Software Engineer", company="Acme Corp")
    analysis = {
        "must_haves": ["Python", "APIs"],
        "nice_to_haves": ["AWS"],
        "what_they_want": "Build services and improve platform reliability.",
        "simplified_requirements": ["Experience building backend services"],
    }

    steps = build_next_steps(job, analysis)

    assert isinstance(steps, list)
    assert any(s["id"] == "apply_now" for s in steps)
    assert any(s["id"] == "research_company" for s in steps)
    assert any(s["id"] == "tailor_resume" for s in steps)
    assert any(s["id"] == "draft_cover_letter" for s in steps)
    assert any(s["id"] == "network_outreach" for s in steps)
    assert any(s["id"] == "schedule_follow_up" for s in steps)
    assert any(s["id"] == "close_skill_gap" for s in steps)


