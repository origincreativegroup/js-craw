# Figma Wireframe Blueprint — Job Search Crawler

This blueprint captures the layout, information hierarchy, and reusable patterns needed to recreate the Job Search Crawler UI inside Figma. Follow these instructions to construct high-fidelity wireframes that reflect the current React/TypeScript implementation.

---

## 1. Figma File Setup

| Setting | Value |
| --- | --- |
| Frame preset | Desktop (1440 × 1024) |
| Layout grid | 12 columns, 72 px gutter, 32 px margin |
| Base spacing | 8 px |
| Primary font | Inter (use Medium 500 for labels, SemiBold 600 for headings, Regular 400 for body) |
| Iconography | Lucide icon set (20 px default in nav, 16 px in controls) |
| Border radius tokens | 6, 8, 12, 16, 20 px (map to `--radius-sm` … `--radius-2xl`) |
| Elevation | Apply drop shadows sparingly (refer to `--shadow`, `--shadow-lg`, etc.) |

Create shared color styles that mirror the design tokens in `frontend/src/index.css`:

- **Primary** `#6366F1` (hover `#4F46E5`)
- **Secondary accent** `#8B5CF6`
- **Success** `#10B981`
- **Warning** `#F59E0B`
- **Danger** `#EF4444`
- **Info** `#06B6D4`
- **Background** `#0F172A`
- **Card Background** `#1E293B`
- **Border** `#334155`
- **Text / Muted** `#F1F5F9` / `#94A3B8`
- **Gradient Primary** (linear 135°, #6366F1 → #8B5CF6 → #EC4899)

---

## 2. Global Layout Shell

Create a base component called **`App Shell`**:

1. **Sidebar (fixed 280 px)**
   - Background: 80% opacity of `#1E293B` with blur.
   - Header block containing logo row (`Sparkles` icon + “Job Crawler” text) and subtitle “AI-Powered”.
   - Vertical nav list with 12 items. Each item: 20 px icon, 14 px label, 12 px vertical padding, 8 px corner radius. Active state uses the gradient primary background, 4 px white left indicator, and slight right shift.

2. **Content Area**
   - Left offset 280 px, max width 1600 px, 32 px padding.
   - Wrap all page frames inside the shell to keep navigation consistent.

All screens should be constructed as components nested inside this shell component.

---

## 3. Reusable Components Library

Create the following base components before drawing pages:

| Component | Description |
| --- | --- |
| `Card / Surface` | 12 px radius, card background, subtle border, inner padding 24 px. Variants: default, gradient header, stat tile. |
| `Button` | Height 40 px (primary) / 32 px (small). Variants: Primary (gradient fill), Secondary (outlined with `#6366F1`), Ghost (transparent with muted text), Icon (circle 40 px). |
| `Tag / Chip` | 24 px height, 12 px horizontal padding, 12 px radius. Variants: Filter, Status (Success/Warning/Danger/Info). |
| `Badge` | 18 px height, pill shape for AI indicators (Sparkles icon + label). |
| `Progress Bar` | 8 px height track with gradient fill. |
| `Table Row` | 56 px height, 12 px inner padding, zebra alternate background. |
| `Metric Stat` | Vertical stack: icon circle (48 px), numeric headline (32 px), label (14 px), optional change indicator. |
| `Timeline Item` | 8 px dot + connecting line, time label, event title, description. |
| `Form Field` | Label 12 px uppercase, input height 44 px, border radius 12 px. Include text area (min-height 120 px). |
| `Stepper Tile` | Number circle, title, description, optional CTA. |
| `Chat Bubble` | Left-aligned assistant (gradient outline), right-aligned user (card background). |

---

## 4. Page Frames

Each subsection below describes a dedicated Figma frame nested inside the `App Shell`. Maintain consistent 32 px vertical rhythm between sections.

### 4.1 Dashboard

1. **Header row**: Title “Dashboard”, subtitle “AI-Powered Job Search - Crawling Companies & Jobs”. Right-align a status pill showing crawler state with a dot indicator (green for running, gray for idle).
2. **Stats grid (4 columns)**: Use `Metric Stat` components for Total Jobs, New Jobs, Applied, Active Searches. Apply color-coded backgrounds (`primary`, `success`, `info`, `warning`).
3. **Content grid (2 columns)**
   - **Top AI-Matched Jobs** card: Header with CTA “View All”. List up to 5 items, each row containing job title, company/location meta, match score pill (color-coded), and AI summary preview.
   - **Crawl Status** card: Header with description. When running, show progress bar, “current company” text, crawl type label, ETA. Idle state shows placeholder copy about next schedule.
4. Optional bottom row for future widgets (leave empty card placeholders).

### 4.2 Discover (AI-curated Jobs)

1. Header: Title “Discover”, subtitle “AI-curated job opportunities tailored for you”.
2. Filter chip row (3 chips: High Match, Recently Found, Ready to Apply) with dual-line labels.
3. Jobs grid: Use `JobCard` component variant with AI summary, Pros/Cons toggle, action buttons (Queue Application, Mark Priority, View Details). Ensure cards stack in two columns.
4. Empty state card with building icon.

### 4.3 Jobs Repository

1. Header row with search bar (icon + placeholder) and segmented filter buttons (All, New, Applied, Rejected, Archived).
2. Body: Masonry-style grid of `JobCard` components (include match circle, AI summary block, pros/cons, keywords chips, posted/found dates, action row with Analyze, Get Next Steps, Chat, External link). Reserve a right-side floating chat drawer overlay for OpenWebUI conversation triggered by “Chat” button.
3. Include `Suggested Steps` popover: vertical list of step cards with CTA “Create Task”.

### 4.4 Apply (Document Generator)

1. Header: Title “Apply Workflow”, subtitle summarizing AI-generated resume/cover letter pipeline.
2. Two-column layout:
   - Left column: `Stepper` cards for process (Review Job → Tailor Resume → Draft Cover Letter → Submit).
   - Right column: `Card` with file upload placeholder for base resume, toggles for “Use AI Enhancements”, buttons for “Generate Resume” and “Generate Cover Letter”, status list with timestamps.
3. Bottom section: table summarizing generated documents (Job, Resume Version, Cover Letter, Status, Actions).

### 4.5 Career Copilot

1. Header with sparkles icon and copy “AI Career Copilot”.
2. Two-column layout: left column shows job/context selector (dropdown, match score). Right column hosts `Chat Panel` (message history, input field, quick action chips for prompts like “Summarize role”, “Draft thank-you email”).
3. Add side cards for “Suggested next actions” and “Profile recommendations”.

### 4.6 Tasks Board

1. Header with CTA button “Add Task”.
2. Overview row: four `Metric Stat` tiles (Open Tasks, Due Today, Completed 7d, Automations).
3. Kanban board (3 columns: To Do, In Progress, Completed). Each card contains task title, related job badge, due date chip, priority indicator, quick actions (mark done, create follow-up).
4. Modal overlay frame for “Create Task” form (fields: Title, Related Job select, Task Type dropdown, Due Date picker, Notes area).

### 4.7 Follow-Ups

1. Header with copy “Maintain recruiter touchpoints”. Secondary CTA “Schedule Follow-up”.
2. Calendar strip (current week) highlighting due reminders.
3. Table listing follow-ups (Job, Contact, Last Interaction, Next Step, Status). Each row includes action icons (Mark Done, Snooze, View Conversation).
4. Side panel showing selected follow-up details with note history.

### 4.8 Companies Catalog

1. Header with search input, filters (ATS type chips), CTA “Import CSV”.
2. Company stats row (Total Companies, Active, Pending Verification, Last Sync).
3. Table view (columns: Company, Platform, Last Crawl, Success Rate, Tags, Actions). Include row actions for “View Jobs”, “Re-run crawl”.
4. Right-side drawer for company details (logo placeholder, metrics, recent job postings list).

### 4.9 Company Discovery Pipeline

1. Header describing automated discovery.
2. KPI strip: Total targets vs active vs pending.
3. Pipeline visualization: three horizontal cards (Collection, Filtering, Verification) with progress meters.
4. Queue list: stacked cards showing companies waiting for verification, each with status chips and “Approve/Skip” buttons.
5. Settings card for discovery interval toggle (switch + numeric input for hours).

### 4.10 Automation & Control

1. Header with summary text “Control job crawling and company discovery”.
2. Grid layout:
   - **Job Crawler** card: status badge, metrics (Run Type, Queue Length, Companies Processed). Button row (Start, Pause, Resume, Stop) with state-dependent disable styles.
   - **Scheduler** card: interval display, next run time, pause/resume toggle, numeric input for minutes, `Update` button.
   - **Discovery Automation** card: metrics (Total Companies, Active, Pending), toggle for “Discovery Enabled”, interval knob.
   - **Health Overview**: chips for Selenium/API/AI crawlers with success percentages and color-coded statuses; timeline list for last runs.
3. Footer banner for logs link (`View Event Stream`).

### 4.11 Filter Profile

1. Header with Save button (primary) and status toast placeholder (success/error).
2. Vertical stack of cards:
   - **Base Resume**: text area or upload drop zone, description text.
   - **Key Skills**: chip list with input to add new skill, each chip has an `X` icon.
   - **Experience**: repeatable list of collapsible panels (Company, Role, Dates, Description). Include “Add Experience” ghost button.
   - **Education**: form fields for Degree, Field, Institution, Graduation Date.
   - **Preferences**: fields for Keywords, Location(s) (multi-chip), Remote toggle, Work Type segmented control, Experience Level dropdown.
3. Sticky footer (within card or page) with secondary button “Reset Changes”.

### 4.12 Settings

1. Two-column layout: left side vertical tabs (General, Integrations, Notifications, API Keys, Advanced). Right side shows selected form.
2. General tab: environment info (Scheduler status, Current Model), toggles for dark mode (pre-checked), input for notification topic, save button.
3. Integrations: cards for ntfy, Pushover, Telegram with status badges and configure buttons.
4. API Keys: table with key name, masked value, created at, copy/delete icons. Include “Generate Key” modal frame.
5. Advanced: dangerous actions block with red outline (Reset Database, Clear Queue).

---

## 5. Auxiliary Screens & States

- **Loading**: full-height center-aligned text “Loading …” using muted text color.
- **Empty State**: Card with centered icon (64 px), headline, supporting text, optional CTA.
- **Toasts**: 320 px width, top-right stack, background `#1E293B`, text white, subtle glow.
- **Modals**: Overlay 40% black, modal width 560 px, 24 px padding, 16 px radius.

---

## 6. Prototype Linking Suggestions

- Sidebar navigation interactions should transition between frames using “Instant”.
- CTA buttons (e.g., “Queue Application”, “Create Task”) link to overlay frames showing success toast or modal.
- Automation buttons animate state change via component variants toggling status badges and disabled states.
- Job cards open external link icon — simulate with tooltip overlay explaining action.

---

## 7. Delivery Checklist

- [ ] All pages share consistent spacing, typography, and component styles.
- [ ] Component variants cover hover/active/disabled states where applicable.
- [ ] Provide annotations for API-driven data (match scores, timestamps, counts) so engineers know required payloads.
- [ ] Export cover frame summarizing the system (title, short description, color legend).

Use this blueprint as the master reference when translating the application’s functionality into a structured Figma wireframe.
