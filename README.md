# MissionControl AI

A nonprofit data analyst with a React/TypeScript dashboard, FastAPI backend, PostgreSQL demo database, bounded SQL tools, and human-approved changes.

**Default development path: private GitHub repository + GitHub Codespaces, entirely in your browser.** The application, database, Docker, and development tools run in the cloud workspace. You do not need to install development tools on your Our House work computer. Use synthetic data only.

Start with **[the browser-only setup guide](docs/SETUP.md)**. It explains how to create your private repository, upload this ZIP inside a Codespace, and apply the included development-container configuration.

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
- `.devcontainer/` configuration, cloud startup script, cloud cost guide, and optional local instructions.

| Folder | Purpose |
|---|---|
| `.devcontainer/` | GitHub Codespaces environment and port forwarding |
| `frontend/` | React, TypeScript, responsive dashboard, Vite |
| `backend/` | FastAPI routes, data model, controlled business logic |
| `agent/` | Tools, demo/live runner, SQL policy |
| `database/` | Seed data, role grants, reference SQL schema |
| `docker/` | Images, Nginx, PostgreSQL setup |
| `scripts/` | Credential setup and cloud startup |
| `tests/` | Workflow, authorization, SQL, and adapter tests |
| `docs/` | Setup, costs, architecture, demo, validation, roadmap |

## Status

Phase 1 (reviewer identities, reevaluation, provenance, reliable live runs, migrations) is checked with 92 backend tests passing on PostgreSQL 16 using the real `mc_reader`/`mc_app` roles (88 on SQLite, where the 4 PostgreSQL role tests are skipped), a successful frontend build, a browser walkthrough of the review flow, and an upgrade of a v0.1 PostgreSQL database. See [phase 1 update](docs/PHASE1_UPDATE.md). The new cloud scripts/configuration have been checked locally, but a real Codespace and full Docker/PostgreSQL startup have not yet been run. See [validation](docs/VALIDATION.md).

Vultr hosting, Microsandbox, and MCP remain later milestones. Codespaces is the development workspace, not the final hackathon hosting platform. No repository, paid Codespace, or cloud server has been created by this ZIP update.

Optional personal-machine development: [local setup](docs/LOCAL_SETUP.md).
