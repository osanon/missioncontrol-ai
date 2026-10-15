# MissionControl review workflow update

Prepared October 9, 2026. This patch is based on the MissionControl_AI_v0.1.zip supplied for this project. It changes application code, not the Codespaces devcontainer.

## What changes

- Missing exit dates: choose a confirmed exit date or reactivate the specific enrollment after confirmation.
- Exit-before-entry findings: enter a corrected exit date, which must not precede entry or be in the future.
- Wage outliers: enter a confirmed wage within the demo $1–$200 range, clear the unverified wage with follow-up, or request follow-up without changing it.
- Negative service units: enter confirmed nonnegative units or request follow-up.
- Possible duplicate clients: follow-up only. No automatic merge or identity changes.
- Every correction is a pending proposal until separately approved with the reviewer token.
- Pending Review shows readable field comparisons, current client/program labels and supporting confirmation notes.
- Existing review-only proposals retain their original historical snapshots. Their current source context is separately labeled.
- Choose correction / Replace proposal supersedes the existing pending proposal, preserves its ID and original values, records the replacement in the audit log, and creates a new pending proposal.
- Rejected or previously applied follow-up proposals can be followed by a new proposal when the underlying issue remains. Previous decisions are preserved.
- Approval checks the entire captured source record, preventing application if the record has changed since proposal creation.
- Existing follow-up flags are preserved on corrections because they may concern other issues. Resolving the source finding does not automatically clear a flag.
- Live AI uses the same controlled proposal logic and has no approval tool. It can propose supplied or sourced values, but does not have a new evidence-retrieval system or automatic date inference. Demo chat remains the guided demo.

## Install in the existing Codespace

1. Download `MissionControl_Review_Update.zip` and upload the actual ZIP into the repository Explorer. Do not create an empty file with that name.
2. In the terminal at the repository root, run:

```sh
python3 -m zipfile -e MissionControl_Review_Update.zip /tmp/missioncontrol-review-update
python3 /tmp/missioncontrol-review-update/install.py .
```

The installer first checks every target file. It stops before editing if any file differs from the expected source version. It also verifies the payload, backs up original files under `.backups/review-update-...`, and is safe to run again. It does not modify `.env`, `.devcontainer`, package dependencies, databases or credentials. Keep the installed ZIP out of Git (the existing project ignores ZIPs).

3. Run the PostgreSQL checks in a separate temporary Docker project:

```sh
bash scripts/check-review-update.sh
```

Expect **46 passed**, with no skipped PostgreSQL tests. A deprecation warning about Starlette/httpx is not a test failure. If tests fail, keep the output and stop before starting the updated app. This script creates and cleans up only its own uniquely named test database/volume; it does not change the running demo data. The first test build downloads/builds a test image and can take several minutes.

4. Build and start the application:

```sh
bash scripts/cloud-start.sh
```

This runs the updated bootstrap job, which adds narrowly scoped database permissions for enrollment status/end-date changes, unit corrections and proposal revisions. It preserves the existing populated database. A successful seed job exits with code 0. Expect a healthy database/backend and a running frontend. No Codespaces Rebuild Container or Full Rebuild is required.

5. Refresh the app browser tab (Ctrl+Shift+R if old controls remain). Re-enter APP_TOKEN and, for approval/rejection, REVIEW_TOKEN from your existing `.env`. Tokens are held only in page memory.

## Walk through the fix

1. Open Approvals & Audit → Pending Review.
2. An old review-only proposal should say **Needs information / follow-up** and show the original saved flag plus separately labeled current source fields.
3. Select **Choose correction**.
4. Choose **Enter confirmed exit date** or **Reactivate this enrollment**. Enter a date when needed and describe the source or program confirmation. These are fictional demo records, so use a clearly identified simulated confirmation for testing.
5. Inspect the comparison before selecting **Replace proposal**. This only creates a new pending proposal. The original appears as superseded in Decision history.
6. Review the new proposal. With the reviewer token, select **Approve & apply** to make the exact displayed change or **Reject** to leave the source record unchanged.
7. Check Data Health, Decision history and Audit log. Rejected issues remain available for a new proposal. Approved corrections remove the relevant finding when its detection condition is no longer true.
8. If information is unavailable, select **Needs information / follow-up**. Approval is labeled **Mark for follow-up**, and it does not supply missing data.

## Save the update to GitHub

```sh
git add backend/logic.py backend/main.py database/bootstrap.py agent/runner.py frontend/src/App.tsx frontend/src/CorrectionReview.tsx frontend/src/style.css tests/test_corrections.py scripts/check-review-update.sh docs/REVIEW_UPDATE.md
git commit -m "Add confirmed corrections and readable proposal review"
git push
```

## Files changed

| File | Purpose |
|---|---|
| backend/logic.py | Validated corrections, complete snapshots, replacement history, context and stale approval protection |
| backend/main.py | Typed request fields and enriched proposal responses |
| database/bootstrap.py | Database role grants for the new controlled writes |
| agent/runner.py | Live tool contract for explicit resolutions and evidence; no approval tool |
| frontend/src/App.tsx | Wire Data Health, correction form and proposal cards |
| frontend/src/CorrectionReview.tsx | New resolution form and human-readable comparisons |
| frontend/src/style.css | Responsive form and comparison styling |
| tests/test_corrections.py | New regression checks |
| scripts/check-review-update.sh | Separate PostgreSQL integration test project |
| docs/REVIEW_UPDATE.md | These instructions and validation scope |

## Validation

- TypeScript compilation and Vite production build: passed.
- Python/API tests with a fresh SQLite database: **44 passed, 2 skipped** (PostgreSQL-only tests).
- Tests cover confirmed dates, reactivation, numeric corrections, missing evidence, invalid/future dates, authorization, rejection, apply-once behavior, old proposals, superseded decisions, stale source rollback and the live proposal tool without an approval tool.
- Browser workflow: legacy replacement, reviewer authorization, approval, preserved history, reactivation proposal and rejection passed. Desktop and mobile screens checked; no browser errors or page overflow.
- PostgreSQL/Docker checks must be run in Codespaces using the supplied test script. They could not be executed in the build environment.
- Live model requests have not been made. The provider loop remains tested with a mock, and proposal dispatch is tested directly.

## Recovery

If the installer says **Stopped without changing files**, send the listed filenames for a tailored patch. Do not force an overwrite.

The installer prints the source-backup folder. To restore code from that backup, first preserve any later edits, then copy the backed-up files to their matching repository paths and remove only newly added update files listed with `existed: false` in the backup's `restore-manifest.json`. Rebuild the application after restoring code. A code rollback does not undo decisions already applied to the database; their audit history remains.
