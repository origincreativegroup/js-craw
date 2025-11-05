# OpenWebUI Full Dataset Context Integration Plan

## Overview
The OpenWebUI integration currently forwards a single job payload to the chatbot, preventing the assistant from referencing the broader job-search records maintained across the application's database tables. This document details a comprehensive plan to expose the complete dataset—including jobs, companies, tasks, follow-ups, applications, generated documents, and crawl history—to the chat layer while maintaining secure, maintainable architecture.

## Current Limitations
- **Narrow payload**: `OpenWebUIService.send_context_to_openwebui` triggers `/api/openwebui/send-context`, which only sends the job currently in focus.
- **Fragmented data**: Related entities (e.g., `Company`, `Application`, `FollowUp`, `Task`, `GeneratedDocument`, `CrawlHistory`) remain inaccessible, leaving the chatbot without critical context.
- **Prompt constraints**: `_format_context_prompt` expects a single-job payload, so even manual attempts to inject more information are difficult to maintain.

## Proposed Architecture
1. **Aggregation service**: A dedicated service composes a holistic view of the job-search dataset using SQLAlchemy models defined in `app/models.py`. The service preloads relationships to minimize query counts and returns a structured payload designed for prompt assembly.
2. **API exposure**: A FastAPI endpoint returns the aggregated payload, guarded by feature flags or authentication hooks currently applied to `/api/openwebui/*` routes.
3. **Prompt transformation**: `OpenWebUIService` gains the ability to recognize both single-job and full-context payloads, summarizing each section (companies, applications, tasks, etc.) for prompt injection.
4. **Frontend orchestration**: The frontend OpenWebUI helpers query the new endpoint when an "All data" context is required, then forward the response through the existing `sendContextToOpenWebUI` workflow.
5. **Documentation**: Operator-facing docs detail configuration and usage patterns, ensuring deployment teams can enable or disable the expanded context safely.

## Implementation Steps
1. **Create an aggregation service**
   - File: `app/services/chat_context_service.py`.
   - Responsibility: Load jobs, companies, tasks, follow-ups, applications, generated documents, and crawl history using eager loading. Provide helper functions to serialize the data into a JSON-safe structure.
2. **Add a FastAPI route**
   - File: `app/api.py`.
   - Endpoint: `GET /api/openwebui/context/full` (or similar), returning the aggregation service payload.
   - Security: Apply existing authentication/feature flag checks used by OpenWebUI endpoints.
3. **Update `OpenWebUIService` prompt handling**
   - File: `app/services/openwebui_service.py`.
   - Extend `_format_context_prompt` to detect a "full context" payload and craft summaries for each data class (e.g., company overview, application status, outstanding tasks).
   - Ensure backward compatibility with the current single-job behavior.
4. **Enhance frontend OpenWebUI utilities**
   - Files: `frontend/src/services/openwebui.ts` and chat-related components.
   - Add a helper to call the new backend endpoint and pass the dataset through `sendContextToOpenWebUI`.
   - Provide UI affordance (e.g., toggle or button) allowing operators to request the expanded context.
5. **Document operator workflow**
   - File: `docs/OPENWEBUI_INTEGRATION.md` (update existing documentation).
   - Describe how to enable the feature flag, request the full dataset, and confirm the chat payload uses the aggregated data.

## Data Shape Considerations
- Normalize output into sections: companies, jobs, applications, follow-ups, tasks, generated documents, crawl history.
- Each section should contain concise summaries plus references (IDs, titles, dates) that the prompt builder can transform into natural language.
- The aggregation service should leverage SQLAlchemy `joinedload`/`selectinload` to avoid N+1 query patterns.

## Security and Privacy
- Apply existing authorization/feature flag checks to the new endpoint to prevent unauthorized access.
- Consider request auditing to track who exports the full dataset.
- If necessary, redact sensitive fields (e.g., personal notes) before returning the payload.

## Testing Strategy
- **Unit tests**: Validate serialization logic in the aggregation service and prompt formatting in `OpenWebUIService`.
- **Integration tests**: Ensure the FastAPI route returns the expected payload and that the frontend successfully retrieves and forwards it.
- **Manual verification**: Trigger the "All data" context from the UI and confirm that the chatbot receives the expanded prompt.

## Rollout Plan
1. Feature-flag the new endpoint and prompt behavior.
2. Deploy backend changes and monitor logs for aggregation performance.
3. Roll out frontend updates to a staging environment for manual validation.
4. Update operator documentation and run a training session if needed.
5. Enable the feature flag in production once confidence is established.

## Future Enhancements
- Add summarization utilities to condense large datasets before prompt injection.
- Implement pagination or filtering for massive record sets.
- Introduce user-level personalization (e.g., limit dataset scope to assigned recruiters).

