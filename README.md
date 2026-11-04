# MissionControl AI

A nonprofit data analyst with a React/TypeScript dashboard, FastAPI backend, PostgreSQL demo database, bounded SQL tools, and human-approved changes.

**Default development path: private GitHub repository + GitHub Codespaces, entirely in your browser.** The application, database, Docker, and development tools run in the cloud workspace. You do not need to install development tools on your own computer. Use synthetic data only.

Start with **[the browser-only setup guide](docs/SETUP.md)**. It explains how to create your private repository, upload this ZIP inside a Codespace, and apply the included development-container configuration.

## Vultr Agent Rush hackathon entry

Entered in **Challenge 2: Powering the Future of Work**. MissionControl runs on a Vultr Cloud Compute instance, which acts as the central backend for the whole workflow: AI agents find data problems, propose fixes and review each other's proposals, people approve, reject or send them back, and every step is audited. Deployment guide: [docs/DEPLOY_VULTR.md](docs/DEPLOY_VULTR.md).

### Project history: what was built before and during the event

This project started before the hackathon. So judges can see exactly what is new, here is what existed before the online build began on 3 November 2026. The full commit history is kept intact so judges can verify it.

**Before 3 November 2026** (commits from 6 October to 2 November):
- The base application: dashboard, metrics, Data Health checks on fictional data, correction and merge proposals with human approval, the audit log, and a demo/live analyst agent with read-only SQL tools.
- Phase 1 (16 October): personal reviewer identities, send back for reevaluation, proposal provenance, saved failed runs, database migrations.
- Phase 2 (24 October): an independent AI reviewer agent and an approval queue that shows AI disagreements first.
- Non-AI preparation (26 October onwards): query performance, browser sessions and a public demo mode, rate limits and an AI budget cap, a demo data reset command, review shortcuts and links, and Vultr deployment scaffolding.
- Development tooling and AI reliability (27 October): automated GitHub checks on every pull request (linting, backend tests on SQLite and PostgreSQL, frontend build), retries and a 150-second time limit for AI provider requests, and the AI agents' instructions moved into readable files (`agent/prompts/`). Missed fixes from 26 October (a migration repair for older databases and a backend image permission fix) were also merged on 30 October.
- Final pre-event polish (30 October – 2 November): an MIT license, repository tidy-up, and a redesigned Ask page (question box first, with the reporting period and key figures in the right-hand column).

**During the event (3–8 November 2026):** listed here as it is built.

- 3 November: deployed MissionControl on a Vultr Cloud Compute instance (Chicago) with public HTTPS, and switched on live AI through Vultr Serverless Inference: `deepseek-v4.1-flash-1017` for the analyst and `glm-5.3` for the independent reviewer, so the second opinion comes from a different model family.
- 4 November: fixes found while testing on Vultr. The analyst is now asked for a written answer, without tools, when it runs out of turns or replies blank (#8), and the reviewer is asked to submit its review on its last turn (#9).

## Once the source is in your Codespace

After `Codespaces: Rebuild Container` completes, run this in the Codespaces terminal:

```sh
bash scripts/cloud-start.sh
```

Open the **Ports** panel, keep port **8080 Private**, and choose **Open in Browser**. Use `APP_TOKEN` from the workspace `.env` file to connect. To approve, reject or send back proposals, add your personal reviewer token (your `name:token` entry in `REVIEWERS` in `.env`) in Connection settings. Add more reviewers with `python scripts/configure.py --add-reviewer NAME`. No model API key is needed for the guided demo.

The generated `.env` is private to the cloud workspace and ignored by Git. `LLM_API_KEY` can later be supplied through a repository-scoped Codespaces secret. Stop the Codespace when finished; closing the browser tab alone is not the stop command.

## Included

- Ask MissionControl: performance summaries, period comparisons, employment/housing cohorts, quality checks, tool evidence, and downloadable Markdown reports.
- Program Performance: period KPIs, program reach, cohort outcomes, and explicit metric definitions.
- Data Health: source records for 56 deliberately planted findings and controlled proposals.
- Approvals & Audit: before/after values, personal reviewer tokens (decisions recorded by name), approve / reject / send back for reevaluation, proposal provenance (person or AI agent, investigation run, model), atomic changes and audit events, stale-record and duplicate-decision protection.
- Reproducible synthetic data: 2,000 fictional clients, six programs, and thousands of related records.
- Live AI adapter: configurable Chat Completions endpoint and model; bounded tool loop; server-side key.
- PostgreSQL roles: initialization owner, read-only analyst, and constrained application account.
- Alembic migrations: schema changes apply automatically on startup and keep existing data. See [phase 1 update](docs/PHASE1_UPDATE.md).
- Independent AI reviewer: checks a pending proposal against the data and gives people a verdict, confidence and concerns; it can never approve or change anything. Runs only when someone selects **Run AI review**. See [phase 2 update](docs/PHASE2_UPDATE.md).
- `.devcontainer/` configuration, cloud startup script, cloud cost guide, and optional local instructions.

| Folder | Purpose |
|---|---|
| `.devcontainer/` | GitHub Codespaces environment and port forwarding |
| `frontend/` | React, TypeScript, responsive dashboard, Vite |
| `backend/` | FastAPI routes, data model, controlled business logic |
| `agent/` | Tools, demo/live runner, SQL policy; AI instructions in `agent/prompts/` |
| `database/` | Seed data, role grants, reference SQL schema |
| `docker/` | Images, Nginx, PostgreSQL setup |
| `scripts/` | Credential setup and cloud startup |
| `tests/` | Workflow, authorization, SQL, and adapter tests |
| `docs/` | Setup, costs, architecture, demo, validation, roadmap |

## Status

Phases 1 and 2 (reviewer identities, reevaluation, provenance, reliable live runs, migrations, and the AI reviewer) are checked with 134 backend tests passing on PostgreSQL 16 using the real `mc_reader`/`mc_app` roles (130 on SQLite, where the 4 PostgreSQL role tests are skipped), a successful frontend build, browser walkthroughs of the review flow, and upgrades of v0.1 and phase 1 PostgreSQL databases. See the [phase 1](docs/PHASE1_UPDATE.md) and [phase 2](docs/PHASE2_UPDATE.md) updates. The app has since been started in a real GitHub Codespace with the full Docker/PostgreSQL stack, and its data edited through Adminer. See [validation](docs/VALIDATION.md).

Vultr hosting, Microsandbox, and MCP remain later milestones. Codespaces is the development workspace, not the final hackathon hosting platform. No repository, paid Codespace, or cloud server has been created by this ZIP update.

Optional personal-machine development: [local setup](docs/LOCAL_SETUP.md).
