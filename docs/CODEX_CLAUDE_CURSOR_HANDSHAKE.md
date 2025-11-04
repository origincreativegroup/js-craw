# Codex ↔ Claude ↔ Cursor Handshake Guide

## Purpose
This guide explains how to make OpenAI Codex, Anthropic Claude, and Cursor collaborate when extending the Job Search Crawler. It maps the code surface area each agent needs, the data they should exchange, and the checkpoints that keep their work in sync. Use it when you want AI assistance to add new crawlers, enrich the AI analysis workflow, or expand the documentation stack without the agents stepping on each other’s toes.

## System Surfaces the Agents Must Share
- **FastAPI lifecycle and scheduler** – `main.py` boots the crawler, registers the scheduler, and exposes the REST API and static dashboard. Any agent scheduling new jobs or adding routes must plug into this file’s lifecycle hooks.【F:main.py†L1-L110】
- **Crawl orchestration** – `CrawlerOrchestrator` coordinates career-page crawls, batches jobs, and triggers AI analysis. Codex and Cursor rely on it for inserting new crawling strategies or downstream processing hooks.【F:app/crawler/orchestrator.py†L1-L125】
- **AI job insights** – `JobAnalyzer` builds prompts, calls the LLM endpoint, and normalizes the response. Claude should use it as the canonical place to adjust summarization formats or add richer reasoning.【F:app/ai/analyzer.py†L11-L189】
- **AI ranking pipeline** – `JobFilter` handles user-profile hydration, prompt construction, scoring, and batch filtering. It is the entry point for blending multiple models or adding guardrails before results are saved.【F:app/ai/job_filter.py†L1-L505】
- **Configuration contract** – `settings` enumerates environment variables that every agent must keep consistent (model hosts, scheduler cadence, notification backends, etc.). Any new secrets for Codex/Claude APIs should be surfaced here so all agents read from the same source.【F:app/config.py†L6-L60】

## Roles and Responsibilities
| Agent | Primary Focus | Required Context |
|-------|----------------|------------------|
| **Cursor** | Orchestrates tasks, keeps repo state synchronized, and stages changes for review. | Needs an up-to-date map of orchestrator and AI modules plus scheduler entry points. Should fetch diffs after every Codex change to maintain a consistent workspace. |
| **Codex** | Implements or edits Python modules (new crawlers, model adapters, DB access). | Consumes prompts curated by Cursor that reference concrete modules (`CrawlerOrchestrator`, `JobAnalyzer`, `JobFilter`). Must read config defaults before adding new env vars. |
| **Claude** | Produces human-facing documentation, prompt templates, and review summaries. | Requires structured outputs from Codex (API signatures, new models) and runtime behavior snapshots from Cursor (logs, tests) before writing docs. |

## Handshake Sequence
1. **Cursor scopes the change**
   - Parse scheduler + orchestrator paths to understand where to wire new behavior.【F:main.py†L27-L83】【F:app/crawler/orchestrator.py†L21-L125】
   - Collect AI pipeline signatures for Codex and Claude (method names, expected return fields).【F:app/ai/analyzer.py†L18-L189】【F:app/ai/job_filter.py†L406-L505】
   - Emit a task brief that includes affected files, feature intent, and guardrails (database schema, API contracts).
2. **Codex implements code changes**
   - Modify or extend orchestrator hooks (e.g., register a new provider) while respecting locking and batch-analysis flow.【F:app/crawler/orchestrator.py†L591-L674】
   - Update `JobAnalyzer` or `JobFilter` to introduce provider selection logic (e.g., route certain prompts to Claude vs. Codex) and ensure results stay normalized before persistence.【F:app/ai/analyzer.py†L18-L165】【F:app/ai/job_filter.py†L217-L353】
   - Surface any new runtime knobs in `Settings` so other agents can discover them automatically.【F:app/config.py†L9-L53】
   - Return diff summaries (file + function level) back to Cursor.
3. **Cursor validates and stages**
   - Run targeted tests or linting tied to touched modules (async orchestrator, SQLAlchemy models, HTTP clients). Capture logs so Claude has ground truth for documentation.
   - Stage commits and provide Claude with the final API signatures and configuration deltas.
4. **Claude documents and reviews**
   - Update or create docs describing new crawlers, AI prompt flows, or configuration flags, citing exact modules for future maintainers.【F:app/ai/analyzer.py†L51-L139】【F:app/ai/job_filter.py†L219-L321】
   - Draft release notes or changelog entries summarizing behavior shifts in orchestrator or AI scoring, referencing scheduler cadence and data flow.【F:main.py†L42-L83】【F:app/crawler/orchestrator.py†L603-L652】
   - Push documentation changes back through Cursor so the repo stays consistent.

## Data Exchange Contract
| Artifact | Produced By | Consumed By | Notes |
|----------|-------------|-------------|-------|
| Change brief (feature scope, file list, constraints) | Cursor | Codex, Claude | Include entry-point functions and relevant env vars. |
| Code diff + unit test output | Codex | Cursor, Claude | Tests should cover orchestrator batches and AI parsing (e.g., `_parse_analysis`, `_parse_match_response`).【F:app/ai/analyzer.py†L107-L139】【F:app/ai/job_filter.py†L355-L404】 |
| Runtime logs (crawl batches, AI queue length) | Cursor | Claude | Helps Claude explain performance implications or rollout plans.【F:app/crawler/orchestrator.py†L603-L647】 |
| Documentation updates (markdown, changelog) | Claude | Cursor | Cursor reviews, stages, and merges alongside Codex code changes. |

## Extending the Handshake to Multiple Models
1. **Provider registry** – Introduce a light-weight provider switch inside `JobAnalyzer`/`JobFilter` that inspects a `provider` field in `settings` (e.g., `AI_ANALYSIS_PROVIDER=ollama|codex|claude`). Keep the default pointing at Ollama to preserve current behavior.【F:app/ai/analyzer.py†L14-L105】【F:app/ai/job_filter.py†L20-L353】
2. **API credentials** – Add optional settings (e.g., `CODEX_API_KEY`, `CLAUDE_API_KEY`) to `Settings`. Cursor ensures `.env` gains matching placeholders, while Claude documents them in the setup guide.【F:app/config.py†L9-L53】
3. **Response normalization** – Keep `_parse_analysis` and `_parse_match_response` as the canonical normalization layers so all providers output the same fields. Codex can extend these helpers with provider-specific clauses; Claude should document any differences.【F:app/ai/analyzer.py†L107-L139】【F:app/ai/job_filter.py†L355-L505】
4. **Batch safeguards** – When mixing providers, let Cursor enforce rate-limit aware batching by adjusting `_batch_analyze_jobs` parameters or inserting provider-aware throttling. Claude should note these limits in operational docs.【F:app/crawler/orchestrator.py†L591-L652】

## Operational Checklist
- **Before coding**: Cursor gathers module signatures and confirms environment variables exist; Claude drafts initial prompt templates if new AI behaviors are required.
- **During coding**: Codex works in small diffs, tests locally, and flags any migrations or scheduler changes.
- **Before merge**: Cursor runs crawl dry-runs or AI batch tests; Claude finalizes documentation; all agents confirm `settings` and `.env` stay synchronized.
- **After merge**: Cursor tags the release, Claude publishes update notes, Codex archives prompts and test artifacts for future reuse.

Following this handshake keeps the three agents coordinated while evolving the job crawler’s AI stack.
