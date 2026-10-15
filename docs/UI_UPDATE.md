# MissionControl UI & Typography Update

Requires the MissionControl Merge Update. Install that update first if you have not already done so. Adminer may be installed before or after this update.

## What changes
- Bundled Inter variable font, larger text, improved contrast, consistent controls and tabular metric numbers. No external font service.
- Data Health: client/program/ID search, issue and priority filters, workflow status counts, pagination and readable record summaries.
- Existing pending proposals open directly in Approvals. One proposal is shown at a time, with its field comparison and saved timestamps.
- Searchable decision history and audit evidence; selectable investigation evidence for each answer.
- Reporting dates apply to analysis/performance, while Data Health covers all records.
- Mobile bottom navigation and accessible connection settings.

## Install in Codespaces
1. Upload MissionControl_UI_Update.zip to your repository root.
2. Run:

```sh
python3 -m zipfile -e MissionControl_UI_Update.zip /tmp/missioncontrol-ui-update
python3 /tmp/missioncontrol-ui-update/install.py .
bash scripts/cloud-start.sh
```

If the installer reports conflicting files, stop and share the file list. It makes no changes when conflicts are found. Do not force an overwrite.

3. Refresh the app preview with Ctrl+Shift+R. Re-enter APP_TOKEN; enter REVIEW_TOKEN only when testing review decisions. Tokens are cleared by reload.
4. Check Data Health filters and Approvals using synthetic records. Confirm dates and current/proposed values before approving.

An application container rebuild is required; a full Codespaces rebuild is not. The installer does not modify .env, .devcontainer, the database, Adminer or approval rules. It backs up replaced files under .backups/ui-update-<timestamp>. No dependency or backend changes.

## Save to GitHub
```sh
git status --short
git add frontend/src/App.tsx frontend/src/CorrectionReview.tsx frontend/src/MergeReview.tsx frontend/src/Workbench.tsx frontend/src/style.css frontend/src/assets/inter-latin-variable.woff2 frontend/src/assets/Inter-OFL.txt docs/UI_UPDATE.md
git commit -m "Improve MissionControl interface and typography"
git push
```

## Validation
TypeScript and Vite production build passed. Browser checks use synthetic SQLite data and cover the bundled font, evidence, data-health search/filter/pagination, existing proposal routing, reviewer gate, correction approval, merge rejection, history/audit and mobile navigation/settings. Docker/PostgreSQL are not run in the packaging environment. The backend is unchanged; prior backend validation remains a separate check in Codespaces.

Inter is distributed under the SIL Open Font License; see frontend/src/assets/Inter-OFL.txt.
