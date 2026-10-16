# Optional local development setup

The default workflow is now [GitHub Codespaces](SETUP.md). Use this guide only if you later choose a personal/local development machine.

## 1. Prepare your computer

Install Docker Desktop (or Docker Engine + the Compose plugin on Linux). Make sure Docker is running. Install Python 3.12+ to run the small setup script; all backend dependencies run inside Docker. For code editing, install Git, VS Code, and Node.js 22 LTS or later.

Download and extract the source ZIP. Open a terminal in `missioncontrol-ai`, the directory containing `compose.yaml`.

Check:

```sh
docker --version
docker compose version
python --version
```

Windows: substitute `py` for `python` if needed. macOS/Linux: substitute `python3`.

## 2. Generate local credentials

```sh
python scripts/configure.py
```

This creates `.env` with randomly generated database passwords, an analyst access token, and a personal reviewer token (`REVIEWERS=reviewer:<token>`; choose the name with `--first-reviewer NAME`, add people later with `--add-reviewer NAME`). It preserves any existing `.env`. Do not commit `.env` to Git. Generated passwords use hexadecimal characters so they work inside connection URLs without escaping.

## 3. Build and start

```sh
docker compose up --build -d
docker compose ps -a
```

The first build downloads dependencies. The database initializes, the one-shot `seed` service creates the schema and fictional records, and the backend starts after seeding succeeds. A completed seed container with exit code 0 is expected.

Open http://localhost:8080. The database and backend are internal to the Docker network; only the frontend is published, bound to your computer's loopback interface.

If startup fails:

```sh
docker compose logs --tail=100 db seed backend frontend
```

If port 8080 is occupied, change the frontend mapping to `127.0.0.1:8081:80` in `compose.yaml`, restart, and open localhost:8081.

## 4. Connect the dashboard

Open `.env` in VS Code or another text editor. Copy only the value after `APP_TOKEN=` into the dashboard's Analyst access token field.

Use the default reporting period July 1–September 30, 2026. Click **Quarterly briefing**. Expand the investigation trail to see the actual tool arguments, results, and SQL sources. Download the report with its evidence.

## 5. Try a controlled correction

1. Open Data Health and search for `wage`.
2. Inspect a source record. Some deliberately incorrect wages are -15 or 1500.
3. Choose Propose review. This creates a proposal without changing the source record.
4. Open Approvals & Audit. Review the before/after fields. A wage proposal clears the unverified value and sets `review_required=true`; it does not invent a correct wage.
5. Add your personal reviewer token (from `REVIEWERS`) through Connection settings and select Verify.
6. Approve & apply, reject, or send back with a note. The audit log records the outcome under your reviewer name.

For duplicates and uncertain dates, the controlled action adds a review flag only. The finding remains visible until the source issue is actually resolved. This MVP allows one proposal per issue key; rejected or stale proposals are retained, and a revision workflow is a planned enhancement.

Tokens remain in browser memory. Reloading requires reconnecting; the database retains proposals, decisions, and investigation records. The chat panel does not yet reload earlier investigations.

## 6. Enable live AI when ready

Edit `.env`:

```dotenv
AGENT_MODE=live
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.4-mini
LLM_API_KEY=your-own-api-key
```

Recreate the backend so it receives the new environment:

```sh
docker compose up -d --force-recreate backend
```

The key stays on the server. The live agent can inspect the schema, issue safe SQL reads, calculate metrics, compare periods/cohorts, scan quality, and propose corrections when asked. It cannot approve a proposal. Each run is capped at six model requests and twelve tool executions. The UI displays the completed trace, not a live stream.

To return to the no-key demo, set `AGENT_MODE=demo` and recreate the backend. Demo mode uses predefined routes selected from the question; it does not claim open-ended language understanding. In demo mode the date picker controls the reporting period; dates mentioned only in text are not parsed.

For another inference provider, set its HTTPS base URL, model, and key. The adapter expects `/chat/completions`, `tools`, strict function schemas, `parallel_tool_calls`, and `max_completion_tokens`. Confirm those options before treating it as compatible; no Vultr inference endpoint has been hardcoded or tested.

## 7. Stop or restart safely

```sh
docker compose stop
docker compose start
```

Or `docker compose down` to remove containers while retaining the named database volume. `docker compose up -d` recreates them.

Changing database passwords in `.env` does not rotate passwords in an already initialized PostgreSQL volume. Rotate the database roles explicitly or, only for a disposable demo you intend to erase, recreate its database volume. Keep your original `.env` alongside the volume.

## 8. Develop without Docker (optional)

The SQLite fallback supports quick local development and unit tests. It does not reproduce PostgreSQL role enforcement or its SQL timeout boundary.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m database.seed
```

Set `APP_TOKEN` and `REVIEWERS` (for example `REVIEWERS=yourname:<random token>`) in your shell, using different random values of at least 24 characters; `.env` is read by Compose, not automatically by direct Python commands. Then run:

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the local Vite address. `/api` requests are proxied to FastAPI. For PostgreSQL local development set `DATABASE_URL` and `READ_DATABASE_URL` to the initialized application and reader connections.

## 9. Initialize your repository

The source is ready for one repository. After extracting:

```sh
git init
git add .
git commit -m "Build MissionControl AI MVP"
```

The included `.gitignore` excludes `.env`, generated local databases, dependencies, and build output. Add your own remote when ready.

## 10. Later: private Vultr demo

Once the Docker PostgreSQL checks pass locally, copy the source and your private `.env` to a Linux VM with Docker + Compose. Build with the same commands. Keep the existing loopback binding and use SSH forwarding for an initial private demonstration:

```sh
ssh -L 8080:127.0.0.1:8080 your-user@your-server
```

Then use localhost:8080 in your browser. No cloud resources are provisioned by this source bundle. A shared public demo needs HTTPS, individual authentication, rate limits, and review of the deployment settings. The current reviewer token identifies a role, not an individual person.
