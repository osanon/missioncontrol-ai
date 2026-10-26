# AI reviews and client workspace

Requires the previously installed Review, Merge and UI updates (the source state committed as 6f2f467 in your repository). Adminer is independent and unchanged.

## Install in Codespaces
Upload MissionControl_AI_Client_Update.zip next to compose.yaml, then run each command in order:

```sh
python3 -m zipfile -e MissionControl_AI_Client_Update.zip /tmp/missioncontrol-ai-client-update
python3 /tmp/missioncontrol-ai-client-update/install.py .
```

If the installer reports conflicts, stop and share the filenames. No files change when preflight fails. Original files are backed up under .backups/ai-client-update-<timestamp>. The installer does not change your credentials, devcontainer or existing database records.

Run the test project, which uses a separate disposable PostgreSQL volume:

```sh
bash scripts/check-review-update.sh
```

After tests pass:

```sh
bash scripts/cloud-start.sh
```

This rebuilds the application and reruns bootstrap to grant the application role permission to update the supported profile fields. It does not reset the data volume. No full Codespaces rebuild is needed. Refresh the port 8080 app with Ctrl+Shift+R and re-enter APP_TOKEN and REVIEW_TOKEN. Keep the port private. Adminer remains on port 8081.

## Clients
Open Clients. Search by name, client identifier or email, then open a profile. The list is paginated, 25 clients per page, with an option to include archived merged profiles.

Profile tabs show enrollments, employment, services, housing, assessments and employment follow-ups. Each tab shows up to 100 records, newest record IDs first, with total counts. Assessments and follow-ups are read-only in this first version. Program labels replace program IDs where possible.

Use Edit profile for name, date of birth and email. Use Edit record for enrollment status/dates, employment dates/wages, service dates/units or housing dates/destination. Enter a reason and Save changes. A reviewer token is required. The application saves the before/after values and reason in its audit log. It refuses stale snapshots, edits to archived profiles, record ownership mismatches and edits affecting pending corrections or merges. IDs and relationships cannot be changed here.

This is a synthetic test-data editor: it deliberately permits values such as negative service units, outlier wages and conflicting dates so you can test Data Health. Required fields, date formats and numeric types are still validated. Blank optional fields become SQL NULL. Save changes applies immediately as an explicit human edit; it is not an AI approval. Refresh Data Health or ask a new question after editing. Previous answers remain historical.

## Live AI configuration
Client browsing and editing work in guided demo. AI review buttons require live mode and your reviewer token. No real provider was called in packaging tests.

Use your provider's API key and a model with Chat Completions tool-calling support compatible with the existing adapter. A ChatGPT subscription is not an API key. Do not paste keys into chat or commit them.

1. Add LLM_API_KEY as a GitHub Codespaces secret with access to this repository (not an Actions secret).
2. Stop and restart the Codespace so its terminal receives the secret.
3. In the existing workspace .env, set AGENT_MODE=live, LLM_BASE_URL to the provider's HTTPS API base URL, and LLM_MODEL to the model identifier enabled for your API account. Keep LLM_API_KEY= blank in .env when using the exported Codespaces secret. For OpenAI, the existing adapter's base URL is https://api.openai.com/v1. Choose an available model rather than copying a placeholder model name.
4. Run bash scripts/cloud-start.sh. If you are only changing model settings after installation and the stack is already running, docker compose up -d --force-recreate backend is sufficient.
5. Confirm the app displays Live AI. Start with one finding. Provider usage is billed separately; the app does not estimate cost or schedule background scans.

The API key stays on the backend. The model receives synthetic finding data, related records returned by read tools and your feedback. Do not enter real client data into this demo.

## Review findings with AI
Open Data Health and select one to three findings. Optional feedback can provide confirmed information. Click Review findings with AI. Requests run sequentially, one finding at a time; keep the page open until completion. A failed request stops the remaining batch. The tool loop is bounded to six model turns and twelve tool calls per finding.

Each result shows an explanation, tool evidence and whether a new proposal was actually saved. No-proposal responses are valid when information is missing or a tool failed. The agent may propose follow-up rather than inventing a date or value. Missing exit dates do not prove active status; a last service date is not an exit date. Matching names and birth dates do not independently confirm duplicate identity.

The model has read and proposal tools, no approval tool and no client-editor tool. Proposal writes are scoped to the selected finding. Use Approvals & Audit to inspect the before/after comparison and approve or reject. The backend revalidates source snapshots before applying changes.

## Feedback and revision
On a pending proposal, click Request AI revision, enter feedback (at least ten characters), then Send feedback & reevaluate.

The server records the revision request before inference. Approval of the old proposal is blocked, even if inference subsequently fails or returns no replacement. Rejection remains available. A successful replacement preserves the original proposal as superseded and retains the reviewer feedback. The new proposal still needs human approval.

If no replacement is produced, provide additional information and retry, use the existing manual replacement form, or reject. A pending merge can be revised within the same profile pair. To switch between a merge and a follow-up proposal, reject the existing proposal first and start a new review. Rejected proposals are not automatically retried; explicitly select their finding if you want a new investigation.

Investigations are saved as agent runs and linked from analysis-completed audit events. The current session also includes AI review answers in Ask MissionControl, where you can export their evidence. Direct client edits and revision feedback appear in Audit log.

## Save to GitHub
After installation, tests and the rebuild succeed, run:

```sh
git status --short
git add agent/runner.py backend/main.py backend/logic.py backend/ai_review.py backend/client_directory.py database/bootstrap.py frontend/src/App.tsx frontend/src/Workbench.tsx frontend/src/CorrectionReview.tsx frontend/src/MergeReview.tsx frontend/src/AIReviewPanel.tsx frontend/src/ClientDirectory.tsx frontend/src/style.css tests/test_agent_workspace.py tests/test_corrections.py docs/AI_CLIENT_WORKSPACE.md
git commit -m "Add supervised AI reviews and client workspace"
git push
```

## Validation and limits
Automated backend tests cover permissions, stale edits, pending-proposal conflicts, scoped AI writes, correction and merge revision, failed inference, approval blocking and preserved history. Model responses are simulated for these checks. Frontend TypeScript/build and desktop/mobile browser flows are also checked. The separate Codespaces test project includes PostgreSQL-specific checks, including the new column grants; those require Docker and are not executed in the packaging environment. Verify one real provider request after configuring live mode.

This is still the synthetic demo with shared role tokens, not production individual accounts or a production client-management system. There is no automatic background scan, auto-approval, client creation/deletion, or one-click undo in this update.
