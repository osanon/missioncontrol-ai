# Architecture and design decisions

Development now runs in a private GitHub repository + GitHub Codespaces. The browser editor and private port-8080 preview are the work-computer interface. `.devcontainer/devcontainer.json` configures the cloud workspace; the existing Compose application runs inside its Docker environment. No connection to Our House production systems is required.

The portable deployment is React + TypeScript → Nginx → FastAPI → PostgreSQL. The agent runner invokes a fixed registry of tools. OpenAI-compatible inference is optional; deterministic guided routes use the same metric, quality, and proposal functions.

## Permission paths

| Operation | Credential / control | Result |
|---|---|---|
| Read dashboard/API | Analyst token | Read metrics, issues, source evidence |
| Agent SQL | Separate `mc_reader` DB login | SELECT only on nine demo tables; read-only transaction; 3-second statement timeout; 200-row output cap |
| Propose change | Trusted tool or analyst API | Pending proposed action with exact before/after fields |
| Decide proposal | Analyst token + personal reviewer token | Approve, reject or send back; decision recorded under the reviewer's name in one transaction with the audit event |
| Initialize schema and seed | Separate owner credential in one-shot container | Creates tables, inserts fictional data, grants roles |

The model never receives the database URL, reviewer token, arbitrary write tool, shell, or Python executor. SQL is parsed with SQLGlot; only one SELECT query, approved tables, grammar nodes, and approved functions are accepted. The database role provides a second boundary. Quality scans and fixed KPI queries are trusted application code.

Approval checks are on the backend. Hiding a button is not the permission control. Pending proposals are locked, claimed once, and applied with a comparison against the original field values. A mismatch aborts the transaction. Rejection writes a decision without changing the record. Audit history cannot be updated or deleted by the application role; a database administrator still controls the database, so this is not tamper-proof storage.

## Recommended changes incorporated

1. **Separate demo and live modes.** An offline guided flow avoids dependence on provider credentials for a first walkthrough. Live behavior remains clearly distinguishable.
2. **Define metrics first.** Every KPI has a period, denominator, and exclusion rule. Program counts overlap and new jobs count records, while cohort outcomes count distinct people.
3. **Use review flags for uncertain facts.** Duplicate identity matches do not trigger merges. Missing dates are not guessed. Outlier wage corrections clear an unverified value only after approval, preserving the old value in the audit record.
4. **Keep data owner privileges outside the application.** The API can update only the review fields and wage field needed by the first version, plus proposal decision fields.
5. **Deliver the core before the sandbox.** A read-only SQL role is not a microVM. Microsandbox integration remains a separate milestone and is not advertised as already implemented.

## Data model

Nine analyst-visible tables: clients, programs, enrollments, services, employment, housing, assessments, followups, surveys. Three control tables: proposed_actions, audit_records, agent_runs. `backend/db.py` is authoritative. Schema changes are Alembic migrations in `database/migrations/versions/`, applied by the seed container (`database.bootstrap`) on every start; a test fails if the migrations and `backend/db.py` disagree.

Dates use ISO `YYYY-MM-DD` strings in this first version to keep the SQLite test fallback aligned with PostgreSQL, while permitting intentionally invalid chronology. Migrate to typed dates and a separate raw/staging layer before importing external data. The data is intentionally fictional and is not a model of Our House's actual performance or schema.

## Execution evidence and reporting

Each completed investigation stores its question, answer, mode, tool arguments, outputs, status, and durations. The report endpoint exports these as Markdown. A live agent's narrative may still be wrong; the evidence trail is the review surface. SQL result truncation is explicit. The previous completed question and answer are passed to the next live request; full multi-turn tool context and saved-chat browsing are planned.

## Proposal lifecycle and provenance

Every proposal records who created it (`created_by`, and `created_by_kind` = `human` or `agent`), and for agent proposals the investigation (`run_id`) and `model`. A human reviewer decides:

- **Approve** → `applied`; the change is made.
- **Reject** → `rejected`; nothing changes.
- **Send back** → `reevaluation_requested` with a required note; nothing changes. The author (today the analyst, later the proposing agent) submits a revision with `replaces_id`; the new proposal records `supersedes_id` and the audit log records `proposal_revised`.

An author can never decide their own proposal. Investigations are always stored, including failed ones (`agent_runs.status = failed`, with the partial trace), so a proposal created before a provider failure still links to its evidence.

## Current scope boundaries

- One fictional PostgreSQL source. No FileMaker, HMIS, Qualtrics, or external source connector yet.
- Reviewers use personal tokens from `.env` (`REVIEWERS`), resolved in `backend/reviewers.py`; Google/Microsoft sign-in is planned and only needs to replace that module. The analyst token is still shared.
- Tools run in the backend with DB-level read isolation. No arbitrary code execution, Microsandbox, MCP transport, or Kubernetes.
- No automatic record merges, inferred dates, or invented demographics.
- One active proposal per issue key; earlier revisions stay in history linked by `supersedes_id`. No bulk approval yet.
- No streaming, background queue, retry scheduler, or production retention policy.

## Microsandbox / MCP next milestone

Add an execution adapter behind the tool registry after verifying the host and current vendor API. Use a short-lived sandbox with CPU, memory, runtime, and output limits. Give it a scoped read-only query gateway, not owner or application credentials. Do not put approval execution inside the sandbox. Only explicitly allowlisted MCP tools should be exposed. Test egress denial, timeouts, oversized outputs, and expired credentials before making sandbox claims in the hackathon demo.
