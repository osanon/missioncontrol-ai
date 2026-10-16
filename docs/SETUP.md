# Browser-only cloud development setup

Use a **private GitHub repository and GitHub Codespaces**. Your work computer needs a browser and internet connection; the development tools and PostgreSQL run in the cloud. Keep this project separate from Our House systems and use only the included fictional data. Vultr deployment comes later.

## 1. Choose the account and review usage

Sign in to the GitHub account you intend to own the hackathon repository. A personal account is the simplest path for this independent synthetic-data project. If using an organization account, its Codespaces access and billing policies may differ.

Review GitHub Settings → Billing and licensing and Settings → Codespaces. Start with a 2-core machine. Review spending controls and set a short idle timeout, such as 15–30 minutes. See [COSTS.md](COSTS.md) for current included usage and estimates. You do not need a separate Vultr subscription for this step.

## 2. Create a private repository

1. Go to https://github.com/new.
2. Name it `missioncontrol-ai`.
3. Select **Private**.
4. Add a README so the repository has an initial commit.
5. Create the repository.

Do not upload a `.env` file, model API key, real client records, FileMaker exports, or Our House credentials.

## 3. Open your first Codespace

On the repository page, select **Code → Codespaces → Create codespace on main**. Use the browser editor. Choose a 2-core machine if asked; use 4 cores later only if build performance warrants it.

This first launch uses GitHub's default development image because the project files are not uploaded yet. Wait for the editor and terminal to finish starting.

## 4. Upload and extract the ZIP in the cloud

Download the updated `MissionControl_AI_v0.1.zip` from this conversation. In the browser Codespace, drag that ZIP into the Explorer pane at the repository root (or use the Explorer's Upload action). Upload the ZIP file itself; you do not need local extraction or development tools.

Open **Terminal → New Terminal**. Confirm the prompt is in your `missioncontrol-ai` repository. Run:

```sh
python3 -m zipfile -e MissionControl_AI_v0.1.zip /tmp/missioncontrol-import
cp -a /tmp/missioncontrol-import/missioncontrol-ai/. .
```

This intentionally replaces the empty repository's starter README and copies the source into the repository root. The root must now contain `compose.yaml`, `README.md`, `frontend/`, `backend/`, and `.devcontainer/`, rather than another nested `missioncontrol-ai` folder.

The uploaded ZIP is ignored by Git. You may delete the uploaded copy from Explorer once the source is extracted.

## 5. Commit the source and apply the cloud environment

In the Codespaces terminal:

```sh
git status --short
git add .
git commit -m "Add MissionControl AI cloud development setup"
git push
```

Use your GitHub identity if Git prompts for one. Check that `.devcontainer/devcontainer.json` was committed. If you prefer, use the browser editor's Source Control panel to commit and sync.

Open the Command Palette with **Ctrl+Shift+P**, search for **Codespaces: Rebuild Container**, and run it. Wait for completion. If the editor labels it **Dev Containers: Rebuild Container**, that is the corresponding rebuild action.

The included configuration adds Docker-in-Docker, forwards port 8080, and generates workspace-only credentials after creation. Docker privileges apply inside this disposable development environment; only add development code and dependencies you trust.

No application build or model call is launched automatically by the post-create script. You start the application in the next step.

## 6. Start MissionControl

Run in the Codespaces terminal:

```sh
bash scripts/cloud-start.sh
```

The script checks Docker, preserves existing credentials, builds the application containers, and starts the database, seed job, backend, and frontend. The first build can take several minutes.

A seed container that has exited with code 0 is expected. Check status or errors with:

```sh
docker compose ps -a
docker compose logs --tail=100 db seed backend frontend
```

If Docker is unavailable, wait for the environment startup or repeat the container rebuild from step 5. Do not install Docker on your work computer to resolve a Codespaces setup issue.

## 7. Open the private app preview

1. Open the **Ports** panel in Codespaces.
2. Find port **8080**, labeled MissionControl AI. If missing, choose Add Port and enter 8080.
3. Confirm **Port Visibility: Private**; do not change it to Public.
4. Choose **Open in Browser** or click its forwarded address.

The address will resemble `https://YOUR-CODESPACE-8080.app.github.dev`. Use that address rather than typing localhost:8080 in your work computer's browser. The service inside the Codespace uses HTTP; GitHub provides the HTTPS browser URL. Keep the forwarded-port protocol at HTTP for the supplied Nginx container.

Private is GitHub's default visibility, but `forwardPorts` by itself is not a visibility policy. Check the actual Ports panel. Only port 8080 is needed; PostgreSQL and FastAPI stay inside the application network.

In the Codespace Explorer, open `.env`. Copy the value after `APP_TOKEN=` into the app's Analyst access token field. To review proposals, copy your personal token (the part after `yourname:` in `REVIEWERS=`) into the app's Connection settings and select Verify. Decisions are recorded under that name. Add a reviewer with `python scripts/configure.py --add-reviewer NAME`, then `docker compose up -d backend`. These tokens are a stand-in until Google/Microsoft sign-in is added. Never commit them or paste them into shared chat.

## 8. Run the no-key demo

Use July 1–September 30, 2026. Click Quarterly briefing, inspect the tool trail, and open Program Performance. In Data Health, inspect a wage issue, create a proposal, then approve or reject it in Approvals & Audit.

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the complete walkthrough. The guided demo makes no model API requests. Date pickers control its reporting period; it does not parse arbitrary dates from question text.

For edits, change the files in the browser editor and rerun `bash scripts/cloud-start.sh` to rebuild. The first version uses container builds rather than automatic hot reload.

## 9. Add live AI using a Codespaces secret

When ready, open GitHub **Settings → Codespaces → Secrets → New secret**. Name it `LLM_API_KEY`, paste your provider key, and grant access only to this repository. This is a **Codespaces** secret, not an Actions secret.

Stop and restart the Codespace so the new secret is available in its terminal. Edit the workspace `.env` file:

```dotenv
AGENT_MODE=live
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.4-mini
LLM_API_KEY=
```

Keep the `.env` key value blank when using the Codespaces secret. Docker Compose reads the exported terminal variable, which takes precedence over the blank `.env` entry. Do not put the key in a Dockerfile, devcontainer.json, or frontend configuration.

Run:

```sh
docker compose up -d --force-recreate backend
```

If the stack is not running yet, use `bash scripts/cloud-start.sh` instead. Live inference is separately billed by your model provider. The tool loop permits read investigations and proposals; the model cannot approve changes.

To return to the guided demo, set `AGENT_MODE=demo` and recreate the backend. Another inference provider needs an HTTPS Chat Completions-compatible endpoint that accepts the adapter's tool and token-limit fields. Vultr inference compatibility has not been verified.

## 10. Save work and stop costs

Commit and push code changes before ending a session:

```sh
git status --short
git add .
git commit -m "Describe your changes"
git push
```

If there are no changes, skip the commit. Generated `.env` files, dependency folders, local databases, ZIPs, and `.backups/` are ignored. The PostgreSQL data volume and ignored files are not backed up by a Git push.

Stop the app containers with `docker compose stop`, then use **Codespaces: Stop Current Codespace**, or Stop on https://github.com/codespaces. Closing the browser tab alone does not immediately stop compute.

To resume, reopen the same Codespace and run `bash scripts/cloud-start.sh`. Keep the existing `.env` while reusing its database volume; changing those passwords in `.env` alone does not rotate PostgreSQL credentials.

Treat the development database as disposable. Before deleting/rebuilding a Codespace, push code and export any reports or demo history you want to keep. A new Codespace generates fresh credentials and can seed a new synthetic database. Storage remains chargeable while a stopped Codespace exists; deleting it removes uncommitted/ignored files and its development data.

## 11. Validate PostgreSQL inside the cloud workspace

Follow [VALIDATION.md](VALIDATION.md) to run the separate `missioncontrol-check` Docker project. It exercises PostgreSQL without changing your main demo's volume. The supplied runtime checks still need to pass on an actual Codespace.

## 12. Deploy to Vultr later

Keep Codespaces for editing and testing. After the Docker checks and live inference work, deploy the same application to Vultr and then add the verified Microsandbox/MCP layer. This ZIP does not provision cloud resources. Kubernetes remains a stretch goal.

## Official references

- https://docs.github.com/en/codespaces/overview
- https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace
- https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces
- https://docs.github.com/en/billing/concepts/product-billing/github-codespaces
