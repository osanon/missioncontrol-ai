# Validation record

Build: MissionControl AI 0.1.0 with cloud-development configuration update, October 5, 2026 UTC.

The application results below are from the original build. This update changes setup/configuration only. The new devcontainer JSON, shell syntax, idempotent credential setup, startup-script behavior with a stub Docker command, and archive contents were checked. No real GitHub Codespace was provisioned; Codespaces launch, Docker-in-Docker, and its forwarded preview remain unverified until the cloud smoke test.

| Check | Result |
|---|---|
| TypeScript compilation and Vite production build | Passed |
| Python/API tests with SQLite fallback | 23 passed |
| PostgreSQL reader-role test | 1 skipped; PostgreSQL runtime unavailable here |
| Browser login and dashboard data load | Passed |
| Ask → real metric tools → evidence trail | Passed |
| Program Performance navigation | Passed |
| Data Health → proposal → reviewer approval → audit | Passed |
| Browser JavaScript errors during walkthrough | None |
| Mobile layout at 390px | No horizontal document overflow |
| PostgreSQL schema compilation | Passed, 12 tables |
| Compose YAML parsing | Passed |
| Docker images and full Compose startup | Not executed; Docker is not installed in this build environment |
| Live model requests | Not executed; provider adapter tested with a mocked response |
| Vultr deployment / Microsandbox / MCP | Not implemented or tested |

The Python tests cover the deterministic seed, metric denominators, cohort distinct-client counts, SQL injection/write rejection, result caps, authentication, missing reviewer credentials, apply-once decisions, idempotent proposal creation, rejection without a source mutation, stale-record rollback, reporting, and the live tool loop using a mock provider.

The frontend was checked in an actual headless Chromium browser against the running FastAPI backend using SQLite. Screenshots are in `docs/images/`. This proves the UI/API workflow, not PostgreSQL grants or Docker image behavior. A Starlette deprecation warning appears in the test run for its httpx test-client integration; it did not fail the tests.

## Repeat the unit tests

For optional Python-level checks, create a virtual environment inside the Codespace. The main Docker integration suite below needs no local computer installs:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r tests/requirements.txt
python -m pytest -q
```

## Run the PostgreSQL integration suite in a disposable Docker project

Generate `.env` first. These commands create a separate project named `missioncontrol-check`, with its own volume. Use a fresh test project; some tests deliberately modify the seeded records.

```sh
docker compose -p missioncontrol-check -f compose.yaml -f compose.test.yaml run --build --rm tests
```

The test suite should report 24 passed when the PostgreSQL checks succeed. If it fails, inspect the output before using the cloud deployment instructions.

Remove only this disposable test stack and its test volume afterward:

```sh
docker compose -p missioncontrol-check -f compose.yaml -f compose.test.yaml down -v
```

Do not substitute your main project name into the cleanup command if you want to preserve its demo data and audit history.

## Manual smoke test after Docker startup

1. Confirm `docker compose ps -a` shows a healthy database/backend and a seed exit code of 0.
2. In Codespaces, open port 8080 from the Ports panel with Private visibility, then connect with `APP_TOKEN`.
3. Confirm the source card identifies PostgreSQL.
4. Run the quarterly briefing and inspect the evidence.
5. Create an outlier-wage proposal; verify approving without a reviewer token is unavailable.
6. Supply `REVIEW_TOKEN`, approve once, and verify the audit event and changed source value.
7. Restart the stack and confirm the decision persisted.
8. Enable live inference and run the prompts in DEMO_SCRIPT.md. Confirm queries and narrative agree with the evidence.
