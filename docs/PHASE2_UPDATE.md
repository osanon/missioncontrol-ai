# Phase 2 update: independent AI reviewer and approval queue

Phase 2 adds a second AI agent that checks proposals before people decide. People still make every decision: approve, reject, or send back.

## What changed

**AI reviewer agent** (`agent/reviewer.py`). For a pending proposal, the reviewer:
- reads the proposal, the current source record and the database (read-only SQL, same limits as the analyst);
- does **not** see the proposing agent's conversation, so it has to check the claim independently;
- submits one review: a verdict (*agrees*, *disagrees* or *unsure*), a confidence (low/medium/high), a short summary and a list of concerns.

Its only output is that review. It has no tool to propose, approve, reject or change data, and its review never changes a proposal's status. Proposal text and database contents are treated as untrusted data, not instructions.

**Demo and live modes.**
- **Demo** (`AGENT_MODE=demo`, no API key): deterministic checks that a careful reviewer would make:
  - a stale record (changed since the proposal) → *disagrees*;
  - services recorded after a proposed exit date → *disagrees*;
  - no activity supporting a reactivation → *unsure*;
  - unusually high service units → *unsure*;
  - merge profiles with different contact details → *unsure*;
  - follow-up flags and clearing an implausible wage → *agrees*.
  
  It always notes that cited evidence is a claim it cannot verify.
- **Live**: uses the model in `LLM_REVIEW_MODEL` (defaults to `LLM_MODEL`), so you can have a different model check the proposer's work.

**Runs only when asked.** The reviewer runs when someone selects **Run AI review** (or **Re-run AI review**) on a proposal. In live mode the button says it uses AI tokens. Phase 3's health-check button will chain the proposer and reviewer automatically.

**Approval queue.**
- Each proposal shows an AI badge (*AI disagrees · high*, *AI unsure*, *AI agrees*, *Not AI-reviewed*).
- Pending proposals are sorted with AI disagreements first, then *unsure*, then unreviewed, then agreements, so dissent is never buried. There's a filter by AI verdict.
- The proposal detail shows the AI review panel: summary, concerns, model or demo rules, and **How the reviewer checked this** (its step-by-step trail).
- **Send back** pre-fills your note from the AI's concerns when it disagreed or was unsure. You can edit or replace it.

**Recording.**
- Every review is saved as an agent run (`kind = reviewer`) with its trail, status and token usage, including failed attempts. Analyst runs now record token usage too, which phase 3's cost limits will use.
- Review history is kept; the latest review is shown.
- When a person decides, the audit log records what the AI had said (`ai_verdict`), so you can later measure how often people agree with or overrule the AI.

**Other changes.** The shared AI-call code moved to `agent/llm.py` (provider config, validated tool loop, token accounting, saving runs). New endpoints: `POST /proposals/{id}/ai-review` and `GET /runs/{id}`. If the AI provider fails, the API returns 502 and the attempt is still saved. Migration `0003_ai_reviews` adds the `ai_reviews` table and the `kind`, `input_tokens` and `output_tokens` columns on `agent_runs`.

## Applying it

Phase 2 builds on phase 1, so apply both together. Follow `docs/PHASE1_UPDATE.md`; the same `docker compose up --build -d` also runs the phase 2 migration. Optionally set `LLM_REVIEW_MODEL` in `.env` for live mode.

## Verification

- All 106 backend tests pass on PostgreSQL 16 with the real `mc_admin`, `mc_reader` and `mc_app` roles; on SQLite 102 pass and the 4 PostgreSQL role tests are skipped. The 14 new tests are in `tests/test_phase2.py`.
- A phase 1 PostgreSQL database was upgraded in place. Existing runs became `kind = analyst`, and only the app role can read or write `ai_reviews`; the AI's read-only SQL role cannot see it.
- Browser walkthrough against PostgreSQL, with the API running as `mc_app`: running a review, a demo disagreement moving to the top of the queue, the review trail, the pre-filled send-back note, and the audit entry showing the AI verdict at decision time. Checked at desktop and phone widths.
- The live reviewer was tested with a scripted provider, not a real model. Not yet run: the full Docker Compose stack in a Codespace.
