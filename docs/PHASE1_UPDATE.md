# Phase 1 update: reviewer identities, reevaluation, provenance, migrations

Phase 1 prepares MissionControl for AI agents that propose and review changes while people approve, reject, or send proposals back. It makes no AI calls and adds no background jobs.

## What changed

**Personal reviewer tokens.** Each reviewer has their own token in `.env`:

```
REVIEWERS=alice:<token>,bob:<token>
```

Decisions and audit events record the reviewer's name instead of a shared "local-reviewer". The browser sends the reviewer token only with decisions, not with every request. The old single `REVIEW_TOKEN` still works and is recorded as the reviewer named `reviewer`. Names like `analyst`, `system` and anything starting with `agent` are reserved so people and AI agents cannot be confused. Someone who authored a proposal can never decide it.

**Send back for reevaluation.** Next to Approve and Reject there is now **Send back**, which needs a short note (at least 10 characters) and changes nothing in the source record. The proposal appears in Decision history as *Sent back* with the note and a **Revise proposal** (or **Revise merge**) button. Data Health shows the finding as *Sent back for reevaluation*. The revision links back to the original (`supersedes_id`), and both stay in history.

**Provenance.** Every new proposal records who created it (a person or an AI agent) and, for agent proposals, the investigation run and model. The review screen shows this above each proposal.

**Reliable live investigations.** A live AI investigation is now always saved, even when the AI provider fails midway or returns a malformed response. Failed runs are marked *Stopped early*, keep their partial evidence trail, and say whether they created proposals that are still waiting for review. The exported report includes the status.

**Database migrations (Alembic).** Schema changes are versioned scripts in `database/migrations/versions/`. The `seed` container runs them on every start (`python -m database.bootstrap`), applies only what the database is missing, and keeps existing data. A database created by v0.1 is detected and upgraded in place. `database/schema.sql` was removed; `backend/db.py` and the migrations are the source of truth, and a test fails if they disagree.

## Apply it to an existing Codespace

Your existing database, proposals and audit history are kept.

1. Pull the branch in the Codespace terminal.
2. Add yourself as a reviewer (your existing `REVIEW_TOKEN` keeps working as `reviewer`):

   ```sh
   python scripts/configure.py --add-reviewer yourname
   ```

3. Rebuild and restart:

   ```sh
   docker compose up --build -d
   docker compose logs seed
   ```

   The seed log should end with `Fictional data initialized; role grants applied.` and the seed container should exit with code 0.
4. Reload the app (Ctrl+Shift+R), connect with `APP_TOKEN`, open Connection settings, paste your personal token from `REVIEWERS`, and select **Verify and close**. The banner shows *Reviewing as yourname*.

To remove a reviewer, delete their `name:token` entry from `REVIEWERS` and run `docker compose up -d backend`.

## Changing the database schema (developers)

1. Edit `backend/db.py`.
2. Generate a migration against an up-to-date database, then read and adjust it:

   ```sh
   DATABASE_URL=sqlite:///./missioncontrol.db python -m database.migrate
   DATABASE_URL=sqlite:///./missioncontrol.db alembic revision --autogenerate -m "describe the change"
   ```

3. If the application role needs to update a new column, add it to the grants in `database/bootstrap.py`.
4. Run the tests. `test_migrations_match_models` fails if the migrations and `backend/db.py` differ.

## Verification

- All 92 backend tests pass on PostgreSQL 16 with the real `mc_admin`, `mc_reader` and `mc_app` roles. On SQLite 88 pass and the 4 PostgreSQL role tests are skipped.
- A v0.1 PostgreSQL database built with the previous bootstrap was upgraded in place; client data was intact, and re-running the bootstrap was a no-op.
- Browser walkthrough against PostgreSQL: reviewer verification, Send back disabled until a reviewer is verified, the note dialog, Decision history with Revise proposal, the revision form showing the reviewer's note, the audit log entry with the note, and the Data Health state. Checked at desktop and phone widths.
- Not yet run: the full Docker Compose stack in a Codespace.
