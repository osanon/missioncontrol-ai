# Duplicate merges and manual database testing

Prepared October 9, 2026. Install after the previous MissionControl Review Update.

## Install in Codespaces

1. Upload the actual `MissionControl_Merge_Update.zip` file beside `compose.yaml`.
2. Run from the repository root:

```sh
python3 -m zipfile -e MissionControl_Merge_Update.zip /tmp/missioncontrol-merge-update
python3 /tmp/missioncontrol-merge-update/install.py .
```

The installer checks the prior review-update file versions, backs up changed source files, and stops before editing if they differ. It preserves `.env` and `.devcontainer`, including the Yarn fix. It does not connect to the database. If it reports conflicts, send the listed filenames rather than forcing an overwrite.

3. Run the isolated PostgreSQL test project:

```sh
bash scripts/check-review-update.sh
```

Expect **65 passed**, with no skipped tests in PostgreSQL. A Starlette/httpx deprecation warning is not a failure. If tests fail, stop here and share the error. The script creates and removes its own uniquely named database volume, without touching the main demo.

4. Back up the current demo before testing merges:

```sh
mkdir -p .backups
docker compose exec -T db pg_dump -U mc_admin -d missioncontrol -Fc > ".backups/demo-before-merge-$(date +%Y%m%d-%H%M%S).dump"
```

Keep the dump in the existing Codespace. `.backups/` is ignored by Git; it is not a remote backup. If pg_dump fails, resolve that error before continuing.

5. Rebuild and start the application:

```sh
bash scripts/cloud-start.sh
```

The updated bootstrap creates the additive `client_merges` table and grants the application permission to move client links. It preserves existing data and decisions. Refresh the app tab and re-enter your existing tokens. No Codespaces Rebuild Container or Full Rebuild is required.

## Use the merge workflow

1. Open Data Health and select **Compare profiles** beside a possible duplicate. This also works if it was already flagged for follow-up.
If identity is not confirmed, **Propose follow-up only** creates a separate review-flag proposal. Already flagged/pending profiles show their existing follow-up state instead.

2. Select a matching profile and choose which profile stays active. Matching name and birth date identify a candidate; they do not prove identity.
3. Review identifiers, names, birth dates, emails, flags and linked record counts. The kept profile supplies the active identity/contact fields. Conflicting contact details remain on the archived profile. This version does not combine individual contact fields.
4. Describe the identity confirmation. For these fictional records, explicitly identify it as simulated confirmation. Check the confirmation box.
5. Select **Create merge proposal**. No client data changes yet.
6. In Pending Review, use the reviewer token to **Approve & merge** or **Reject**. Check Decision history and Audit log afterwards.
7. If data changed while a proposal was pending, approval stops without applying anything. Select **Review / replace merge**, review the refreshed comparison, and submit a new proposal. The older version stays in history.

If either profile has pending corrections to its enrollments, services, jobs, housing or assessments, decide those corrections before proposing the merge. Overlapping pending merges are blocked. Pending profile follow-up proposals are shown in the merge preview and become superseded on approval; existing follow-up flags remain.

## What is merged

- Enrollment, service, employment, housing and assessment records belonging to the archived profile move to the retained client ID.
- Their own record IDs and values remain unchanged. Employment follow-ups stay linked to their original jobs. Program-level surveys are unaffected.
- The archived client row and external identifier are kept. `client_merges` records the source ID, target ID, proposal, reviewer and timestamp.
- Exact duplicate events are **not** deleted. A merge can reduce distinct-person counts while preserving the number of service events, job records and housing exits. Review overlapping events separately.
- Built-in metrics already count linked service/job/housing records. For manual or AI SQL that counts client profiles, exclude IDs present as `client_merges.source_id` to avoid counting archived identities.
- This version supports exact-name-and-birth-date candidates only. Do not edit identity fields merely to force a match.
- A profile that already retains previous merges must remain the target in later merges. This prevents alias chains.
- There is no one-click undo. The original profiles, proposal snapshots and moved record IDs remain in history. A code rollback does not undo applied merges; keep the database backup.

## Where to configure and edit the synthetic database

| Location | Purpose |
|---|---|
| PostgreSQL container `db` | The live synthetic records used by the app |
| `backend/db.py` | Tables, columns, relationships and SQLAlchemy connection setup |
| `database/seed.py` | Initial fictional records for a new, empty database |
| `database/bootstrap.py` | Initial schema creation and database role permissions |
| `backend/logic.py` | Metric definitions and data-quality rules |
| `backend/merges.py` | Merge preview, proposals and approved execution |
| Workspace `.env` | Credentials and runtime/model settings, not client data |

Editing `database/seed.py` and rebuilding does **not** overwrite an existing database: the seed preserves populated data. Do not delete the main volume just to try a different outcome. Editing table declarations also does not automatically migrate existing columns; this update only adds a new table.

Open the current database from the Codespaces terminal:

```sh
docker compose exec db psql -X -U mc_admin -d missioncontrol
```

The prompt changes to `missioncontrol=#`. Enter SQL there, ending statements with `;`. `\dt` lists tables; `\d employment` describes a table; `\q` returns to the normal terminal. No database port needs to be published.

Inspect records before changing them:

```sql
SELECT id, client_id, start_date, hourly_wage
FROM employment
WHERE start_date BETWEEN '2026-07-01' AND '2026-09-30'
ORDER BY id LIMIT 10;

SELECT id, client_id, entry_date, exit_date, destination
FROM housing
WHERE exit_date BETWEEN '2026-07-01' AND '2026-09-30'
ORDER BY id LIMIT 10;
```

### Reversible wage/outcome test

This chooses an existing valid wage from Q3 and remembers its original value in the current psql session. Keep the session open until you restore it.

```sql
BEGIN;
SELECT pg_advisory_xact_lock(641024601);
SELECT id AS test_job_id, hourly_wage AS original_wage
FROM employment
WHERE start_date BETWEEN '2026-07-01' AND '2026-09-30'
  AND hourly_wage BETWEEN 1 AND 200
ORDER BY id LIMIT 1
\gset
UPDATE employment SET hourly_wage = 35
WHERE id = :test_job_id
RETURNING id, client_id, hourly_wage;
COMMIT;
```

Return to the app, set July 1–September 30, 2026, and click **Refresh data**. The average wage should change. You can ask for a new summary as well; old answers remain historical and do not recalculate.

To create a wage quality flag on the same test record:

```sql
BEGIN;
SELECT pg_advisory_xact_lock(641024601);
UPDATE employment SET hourly_wage = 1500 WHERE id = :test_job_id;
COMMIT;
```

Refresh Data Health. The wage should be flagged and excluded from the valid-wage average. Use the app to propose a confirmed correction, or restore the original value from the same psql session:

```sql
BEGIN;
SELECT pg_advisory_xact_lock(641024601);
UPDATE employment SET hourly_wage = :original_wage WHERE id = :test_job_id;
COMMIT;
```

If the selection reports no rows, stop rather than reusing psql variables from a previous test. The supplied seed includes matching jobs. Do not combine this test with another person editing the same job.

### Other outcome scenarios

| Test change | Expected effect |
|---|---|
| Valid Q3 housing exit destination from `unstable` to `stable` | Stable-exit numerator increases; denominator stays the same |
| Move a job's start date outside the chosen reporting period | Job count and wage average may change |
| Set all of one client's in-period positive services to zero | Client is excluded from clients served for that period |
| Set an enrollment to `exited` with `end_date = NULL` | Missing-exit quality finding; does not itself change the housing stable-exit metric |
| Approve a merge for two profiles both served in the same period | Distinct people can decrease; event record counts stay the same |

Use a transaction and inspect `UPDATE ... RETURNING` when editing a selected row. Use `ROLLBACK;` instead of `COMMIT;` if the previewed change is wrong. The app sees edits only after COMMIT. The advisory-lock line coordinates these test transactions with app approvals. Direct administrator SQL intentionally bypasses app proposal approvals and app audit events, so use it only for controlled synthetic tests. Do not edit archived client links, proposals, audit records or merge mappings manually.

Database value changes require **Refresh data**, not an app/container rebuild. Code or seed-logic edits require rebuilding the application; seed changes only affect new empty databases.

## When to connect a live model

After this update's PostgreSQL checks pass and you have verified one approved merge and one rejected merge in the demo, connect live inference. You do not need to wait for Vultr deployment.

The live agent can investigate with read-only SQL, preview a pair, explain conflicts, and create a merge proposal when explicitly asked with identity confirmation. It cannot approve. The same validated backend applies approved changes. The patch adds these tools but does not activate live mode, choose a provider, or call a model.

Use the live-inference section of `docs/SETUP.md` to configure the provider, Codespaces secret and workspace `.env`. Confirm the chosen model identifier and tool-calling support with that provider. Keep synthetic data during testing. Test read-only questions first, then proposal creation, rejection and approval; compare answers to the tool trail and database values.

## Save to GitHub

```sh
git add backend/db.py backend/logic.py backend/main.py backend/merges.py backend/mutations.py database/bootstrap.py database/schema.sql agent/runner.py frontend/src/App.tsx frontend/src/CorrectionReview.tsx frontend/src/MergeReview.tsx frontend/src/style.css tests/test_merges.py docs/MERGE_UPDATE.md tests/test_corrections.py scripts/check-review-update.sh docs/REVIEW_UPDATE.md
git commit -m "Add reviewed duplicate merges and database testing guide"
git push
```

The command includes the prior review update in case it has not been committed yet. Do not stage `.env`, ZIPs or backups.

## Validation and limits

- TypeScript/Vite production build passed.
- Python/API tests: **61 passed, 4 skipped** in SQLite. The four skipped tests require PostgreSQL, including app-role permissions and concurrent approval.
- Browser walkthrough passed: already-flagged duplicate comparison, proposal creation, reviewer gate, approval, saved history, mobile form and rejection; no JavaScript errors or page overflow.
- The live tool loop was tested with a mocked provider, including preview and pending merge creation. No actual model requests were made.
- Run the included PostgreSQL suite in Codespaces before starting the updated main app. PostgreSQL/Docker execution is unavailable in the build environment.
