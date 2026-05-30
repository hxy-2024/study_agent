# Three-Layer Agent Model Design

**Goal:** Define what each agent layer can do, must do, and must not do before adding Main Agent dashboard recommendations.

**Core Rule:** The homepage recommendation is a Layer 1 decision. Layer 2 agents produce structured signals and specialist judgments. Layer 3 agents/tools execute bounded work and return evidence.

---

## Layer 1: Main Agent

**Purpose:** Own the user's learning agenda and decide what should be shown on the dashboard.

**Can do:**
- Talk directly with the user about goals, time available today, fatigue, preferred study mode, and schedule changes.
- Read cross-space learning state: active spaces, route progress, mastery, quiz results, mentor summaries, planner actions, recent sessions, and current time.
- Decide the single best next action for the dashboard.
- Explain why that action was chosen.
- Ask Layer 2 agents for specialist analysis.
- Record the final recommendation as an agent run for auditability and later tuning.

**Must do:**
- Produce one primary dashboard recommendation and a short secondary queue.
- Keep the recommendation flexible: if the user says "I only have 20 minutes" or "I want new material", the Main Agent updates the recommendation.
- Fall back to deterministic rules when the LLM provider is unavailable.
- Keep user-facing output concise, specific, and actionable.

**Must not do:**
- Directly ingest files, retrieve chunks, grade quiz answers, or mutate low-level learning artifacts.
- Hide uncertainty. If the signal is weak, say so and recommend the safest next action.
- Let a Layer 2 or Layer 3 result override the agenda without Main Agent arbitration.

**Initial implementation name:** `main_agent` or `daily_planner`.

---

## Layer 2: Specialist / Supervisor Agents

**Purpose:** Analyze one domain deeply and return structured signals to the Main Agent.

**Current and planned Layer 2 agents:**

- `space_planner`: Reviews a study space, route progress, risk chapters, and route adjustment needs.
- `chapter_mentor`: Summarizes chapter understanding, weak points, next actions, and evidence from mentor sessions.
- `quiz_mastery`: Evaluates quiz outcomes, mastery level, weak points, and retake readiness.
- `review_planner`: Builds spaced-review candidates from mastery, last activity, and chapter status.
- `session_tutor`: Handles one study conversation, but its summarized signal is consumed by Layer 2 or Layer 1.

**Can do:**
- Read and summarize domain-specific state.
- Create proposed actions, risk signals, weak-point lists, and review candidates.
- Call Layer 3 tools for retrieval, grading, citation expansion, or source evidence.
- Write structured outputs into existing state tables or agent run payloads.

**Must do:**
- Return machine-readable output that the Main Agent can compare and rank.
- Include evidence references where possible.
- Stay scoped to its domain.

**Must not do:**
- Decide the homepage's final "today first" action.
- Directly override user preferences.
- Mix unrelated domains into its output.

---

## Layer 3: Tool / Worker Agents

**Purpose:** Execute bounded operations and return facts, artifacts, or evidence.

**Examples:**
- RAG retrieval.
- Source ingestion and chunking.
- Quiz generation.
- Quiz answer scoring.
- Citation/source expansion.
- Web search when explicitly enabled.
- Storage/database helpers.
- LLM provider calls.

**Can do:**
- Execute deterministic or provider-backed tasks.
- Return raw evidence, candidates, generated questions, scored answers, or citations.
- Fail closed with clear error messages.

**Must do:**
- Avoid making agenda-level decisions.
- Return outputs in a stable shape.
- Preserve tenant/user boundaries.

**Must not do:**
- Talk directly to the dashboard as if it were the Main Agent.
- Create hidden user-facing recommendations without a Layer 1 or Layer 2 owner.

---

## Coordination Rules

1. The Main Agent owns dashboard recommendations.
2. Layer 2 agents produce signals, not final agenda decisions.
3. Layer 3 tools produce evidence and bounded artifacts.
4. Every agent run should record:
   - agent type
   - input payload
   - output payload
   - prompt or deterministic strategy version
   - model/provider when applicable
   - latency/token/error metadata when available
5. User interaction always returns to the Main Agent before changing the dashboard recommendation.

---

## Dashboard Recommendation Flow

1. Dashboard requests the latest Main Agent recommendation.
2. If no fresh recommendation exists, the API can generate one.
3. Main Agent gathers:
   - active spaces
   - route/chapter progress
   - mastery and quiz status
   - mentor weak points
   - planner actions
   - recent session/agent activity
   - current time and user-provided available time when present
4. Main Agent asks Layer 2 agents only when existing signals are stale or missing.
5. Main Agent returns:
   - primary action
   - reason
   - estimated minutes
   - action URL
   - secondary queue
   - freshness/source metadata
6. Dashboard displays the result as the main "Today" card.

---

## LangGraph Usage

LangGraph becomes useful when the Main Agent needs multi-step stateful orchestration:

- collect dashboard signals
- ask specialist agents for missing state
- reason over user constraints
- generate a recommendation
- persist checkpointed state
- continue when the user says "change it, I only have 20 minutes"

Initial PR can use a deterministic service with the same input/output contract. LangGraph should be introduced when the Main Agent starts coordinating multiple Layer 2 calls or interactive revisions.

