# UX Strategy for Automated Job Search Assistant

The existing dashboard already surfaces crawler status, AI insights, and automation telemetry, giving us a strong foundation for an end-to-end job-search cockpit. To turn it into a guided job-search-and-application assistant, we will emphasize three pillars:

1. **Automated Discovery:** Make it effortless to define search intents, prioritize companies, and review high-fit matches.
2. **Application Execution:** Provide an integrated workspace for tailoring materials, tracking submissions, and scheduling follow-ups.
3. **Continuous Automation Control:** Keep the Automation Command Center front and center so users can trust that the system is continuously working for them.

---

## 1. Guided Job Discovery Workspace
Users need a single view where they can see top matches, why they matter, and what to do next. Current job cards already show AI insights and metadata but lack prioritization cues, filtering, and next-step prompts.

:::task-stub{title="Design a Guided Job Discovery tab"}
1. Extend `static/index.html` to add a dedicated “Discover” tab that pulls curated matches with match-score badges, highlight badges, and AI insight summaries in the job cards (`.job-card`, `.job-ai-insights`).
2. Introduce filter chips for “High match”, “Recently found”, and “Ready to apply” using the existing `.filter-chips` component, wired to API queries in `app/api.py` to fetch filtered job lists (e.g., `GET /api/jobs?match=high`).
3. Add inline actions on job cards (e.g., “Preview Resume”, “Queue Application”) to bridge discovery with application flows, storing the user’s intent via a new endpoint (`POST /api/jobs/{id}/actions`). Update `app/api.py` to accept these intents and persist them through the `TaskService`.
:::

---

## 2. Application Preparation Hub
After selecting promising roles, users should be guided through tailoring resumes, cover letters, and tracking submissions. The UI already includes resume/cover letter generation indicators (e.g., `.batch-progress`, `.recommendation-card`), but they need a cohesive “Apply” experience.

:::task-stub{title="Create an Application Preparation hub"}
1. Add an “Apply” tab in `static/index.html` that aggregates jobs flagged for application, showing status chips (Queued → Drafting → Applied) and AI-generated recommendations (`.recommendations-list`).
2. Embed a stepper component that walks users through: confirm job requirements, generate tailored resume/cover letter via calls to `app/ai/document_generator.py`, review AI output, and store the generated documents in the database (extend `app/api.py` with `POST /api/jobs/{id}/documents`).
3. Introduce a submission form within the stepper to log actual applications (company portal link, submission date, uploaded artifacts), persisting to a new `Application` model in `app/models.py` and exposing CRUD endpoints in `app/api.py`.
:::

---

## 3. Follow-up and Task Automation
The system already has task and follow-up models, but the UI should make them actionable so users can stay on top of interviews, referrals, and reminders.

:::task-stub{title="Surface automated follow-up workflow"}
1. In the “Apply” tab, add a “Next Actions” sidebar that lists AI-generated tasks from `TaskGenerator` (e.g., schedule referral outreach), leveraging the existing `.task` styling and building on `.recommendation-card` visuals.
2. Allow users to adjust due dates, priorities, and snooze settings directly via buttons that call the existing task endpoints (`PATCH /api/tasks/{id}` and `POST /api/tasks/bulk`). Update `static/index.html` to display quick action buttons (Complete, Snooze, Reschedule).
3. Implement notification toggles per task (notify via ntfy/Pushover/Telegram) by integrating the form controls in `static/index.html` with the notifier service in `app/notifications/notifier.py` (e.g., `POST /api/tasks/{id}/notify`).
:::

---

## 4. Automation Command Center Enhancements
Maintaining trust in automation is critical. The Command Center already describes telemetry, health chips, and control operations. We can elevate it by adding predictive cues and automation recipes.

:::task-stub{title="Enhance the Automation Command Center experience"}
1. Within the Automation tab of `static/index.html`, add microcopy that explains each health chip and provides suggested actions when a crawler degrades (e.g., “Lever crawler error rate >30% — review credentials”). Utilize `.health-chip` states and extend the data pulled from `/api/crawl/status` to include trend info.
2. Visualize upcoming automation tasks (next crawl, next document generation batch) with a timeline or countdown widget next to the automation header, using the existing `.automation-header` block and data from `/api/automation/scheduler`.
3. Add a library of automation “recipes” (e.g., “Aggressive remote search”, “Targeted company blitz”) that pre-fill search criteria via modal dialogs. Store recipe templates in a JSON file and wire them to `POST /api/searches` so users can launch advanced automations quickly.
:::

---

## 5. Onboarding & Settings Refresh
First-time setup should guide the user through connecting accounts, selecting notification channels, and seeding target companies.

:::task-stub{title="Revamp onboarding and settings"}
1. Turn the Settings tab into an onboarding wizard in `static/index.html`, leveraging `.settings-section` visibility controls to guide users step by step (Connect Platforms → Select Notification Channel → Seed Companies → Define Initial Search).
2. Preload recommended companies (from `companies.csv`) with toggles for activation, mapping to the company CRUD endpoints in `app/api.py` (`POST /api/companies`, `PATCH /api/companies/{id}`).
3. Provide real-time validation for credentials using the existing verification routines (call `verify_ollama.py` analogues or new API endpoints) and display inline status chips next to each integration option.
:::

---

## Execution Notes
- **Design Consistency:** Reuse the established card, badge, and modal components to maintain a cohesive aesthetic.
- **Progress Feedback:** Every long-running action (AI document generation, batch resume customization) should use the existing progress indicators (`.batch-progress`, `.progress-bar`) so users feel the system working.
- **AI Transparency:** When AI makes recommendations, include “Why this role?” and “Suggested talking points” inside `.job-ai-insights` to build trust and reduce friction in tailoring outreach.
- **Mobile Responsiveness:** Preserve responsive grids (`.stats-grid`, `.jobs-grid`, `.health-chips-grid`) and ensure new layouts collapse gracefully for smaller screens, keeping automation controls accessible.

By incrementally implementing these UX enhancements, the interface will evolve into a true job-search co-pilot that not only finds opportunities but also shepherds users through every stage of the application lifecycle.
