# Deploying MissionControl on Vultr

This puts the whole stack (web app, API, AI agents and PostgreSQL) on one Vultr Cloud Compute instance, with public HTTPS. Vultr is the central backend: planning, agent runs, approvals and the audit trail all run on this server.

```
Internet ──HTTPS──▶ Caddy (80/443, automatic certificate)
                     └─▶ Nginx: React app + /api proxy (private)
                          └─▶ FastAPI: agents, approvals, audit (private)
                               └─▶ PostgreSQL (private; separate admin, app and read-only roles)
Live AI (optional) ──▶ Vultr Serverless Inference, https://api.vultrinference.com/v1
```

## 1. Vultr account and credits

1. Create an account at [vultr.com/register](https://www.vultr.com/register/) with an email address that has **never** been used with Vultr, and verify it.
2. At the hackathon kickoff (3 November), open [Billing → hackathon promotion](https://console.vultr.com/billing/?promo=HACKATHON) and apply the gift code. You should see $200.00 of credit.

## 2. Create the server

In the Vultr console choose **Deploy → Cloud Compute**:
- **Image:** Ubuntu 24.04 LTS x64.
- **Plan:** 2 vCPU / 4 GB RAM is comfortable (building the frontend needs about 1 GB). 1 vCPU / 2 GB works but builds slowly.
- **Location:** the region closest to you or the judges (for example Chicago or Dallas).
- **SSH key:** add yours, so you don't need a root password.

Note the server's public IPv4 address.

## 3. Install and start

```sh
ssh root@YOUR_SERVER_IP
git clone https://github.com/osanon/missioncontrol-ai.git
cd missioncontrol-ai
bash scripts/vultr-setup.sh
```

The script:
- installs Docker and a firewall that allows only SSH, HTTP and HTTPS;
- creates `.env` with generated passwords and tokens (it never overwrites an existing one);
- sets `DOMAIN` to `YOUR-IP-WITH-DASHES.sslip.io`, a free name that points at your server, so HTTPS works without buying a domain;
- turns on the public demo and a daily AI token budget;
- builds and starts everything.

Open `https://YOUR-IP-WITH-DASHES.sslip.io`. The first certificate can take a minute.

To use your own domain instead, point an A record at the server and run `DOMAIN=demo.example.org bash scripts/vultr-setup.sh` (or edit `DOMAIN` in `.env` and restart).

If the repository is still private when you clone, use a GitHub personal access token or deploy key. It must be public for the submission anyway.

## 4. Settings in `.env`

| Setting | Meaning |
|---|---|
| `PUBLIC_DEMO=true` | The sign-in page shows **Try as analyst** and **Try as reviewer**, so judges need no token. Anyone with the URL can act as the demo reviewer, so use it only with the fictional dataset. Set `false` to require tokens. |
| `APP_TOKEN`, `REVIEWERS` | Your own analyst and personal reviewer tokens. Add a reviewer with `python3 scripts/configure.py --add-reviewer NAME`. |
| `AI_DAILY_TOKEN_BUDGET` | Live AI stops for the day (UTC) after this many tokens; demo mode keeps working. `0` means no cap. |
| `AI_RATE_PER_HOUR`, `LOGIN_RATE_PER_MINUTE` | Per-visitor limits on live AI requests and sign-in attempts. |
| `AGENT_MODE` | `demo` (rule-based, no AI cost) or `live`. |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_REVIEW_MODEL` | Live AI provider. For Vultr Serverless Inference: `https://api.vultrinference.com/v1`, your inference API key, and a model from the [live model list](https://api.vultrinference.com/v1/models). Live use with Vultr Serverless Inference is being validated during the event week. |

After changing `.env`, apply it with:

```sh
docker compose -f compose.yaml -f compose.vultr.yaml up -d
```

## 5. Day-to-day commands

Run these from the project directory on the server. `DC` is shorthand for the compose command:

```sh
DC="docker compose -f compose.yaml -f compose.vultr.yaml"
$DC ps                                   # status
$DC logs -f --tail=100 backend caddy     # logs
git pull && $DC up -d --build            # deploy an update (database migrations run automatically)
$DC run --rm seed python -m database.reset --yes   # reset the fictional demo data, e.g. before judging
```

The reset clears all proposals, AI reviews, runs and audit history, and restores the 56 planted data problems. The web app cannot do this itself, because its database role has no delete rights, which keeps the audit trail append-only.

## 6. Costs and cleanup

Keep an eye on remaining credit in Billing. Instances are billed hourly; the console shows the monthly price of each plan before you deploy, and a 2 vCPU / 4 GB instance for one event week uses a small share of the $200. When you're finished, destroy the instance in the Vultr console. Stopping it does not stop billing.
