# Recommended next build sequence

## Agent-first plan (current)

The target: AI agents find issues, propose corrections and review each other's proposals; people only approve, reject, or send back.

1. **Foundations (done; see PHASE1_UPDATE.md):** personal reviewer identities, send back for reevaluation, proposal provenance, reliable live runs, Alembic migrations.
2. **AI reviewer agent and approval queue (done; see PHASE2_UPDATE.md):** an independent reviewer agent (its only write tool is `submit_review`) checks proposals; the queue puts disagreements first. Runs on demand; phase 3 chains it automatically after proposals.
3. **"Perform health check" button and worker:** the SQL scan stays free; AI work runs only when a person starts it. Runs are recorded with token use and cost, skip findings already handled, stop at a token limit, and can be cancelled. Sent-back items are re-proposed immediately.
4. **"Live health checks" toggle:** an opt-in schedule with a daily token budget, off by default.
5. **Evidence sources and evaluation:** connect the sources agents may cite (for example payroll or case-management exports) and measure proposal precision against the planted anomalies.

## Vultr Agent Rush hackathon (3–8 November 2026)

Entered in **Challenge 2, Powering the Future of Work**. Submissions close **8 November, 5:00 PM CST** on LabLab.

Required: Vultr VM backend (Vultr as the central system, not just static hosting), web app deployed on Vultr with a public URL, a public GitHub repository with setup docs, a README explaining the Vultr services, architecture and agent use case, a demo video, slides and a cover image. Serverless Inference (`https://api.vultrinference.com/v1`) is optional but is used for "Application of Technology". Judging: Application of Technology, Presentation, Business Value, Originality.

## After the hackathon: Challenge 1-style sandboxed execution ("Blast Radius Zero")

A reminder is scheduled for 10 November 2026. Build a web agent whose real work runs inside isolated sandboxes on Vultr, either as a new MissionControl tool (a sandboxed "run analysis code" step, with the proposer, reviewer and human approval as the control layer) or as a separate project.

- **Pattern A, sandboxed code execution:** the user asks → the model writes code → it runs in a container → real output returns → the model explains it; errors feed back for retries.
- **Pattern B, sandboxed browser use:** the user gives a goal → the model plans → Playwright runs in a container → screenshots return → a vision model verifies → a person approves final actions.
- **Containment:** process isolation (never the host or app runtime), no credentials inside the sandbox, time and memory limits on every run, reset or destroy after each task. Docker or gVisor on a Vultr VM is the simplest route (see Vultr's agent sandboxing guide); OpenSandbox, E2B and Microsandbox are alternatives. Use Vultr Serverless Inference for model calls.
- **Demo:** show one "containment moment" where the sandbox absorbs something unsafe.

## Earlier sequence

1. Create the private GitHub repository, load the source into Codespaces, and validate the complete Docker + PostgreSQL deployment with the included disposable integration test configuration.
2. Configure a live model key and run the demo prompts against the real provider. Add token usage/cost accounting and narrative-to-evidence checks.
3. Add proposal revisions and reviewer identities. Keep uncertain corrections separate from automated execution; add typed correction forms with source evidence.
4. Add a dated multi-source staging layer with source IDs and reconciliation rules; keep source-of-truth and deduplication decisions explicit.
5. Integrate the verified Vultr Microsandbox/MCP execution layer. Keep writer credentials and approval execution outside the sandbox.
6. Deploy a private VM demonstration. Add streaming tool events and a saved investigation browser for judges.
7. Add exports/visual reports, background jobs, migrations, and observability. Consider Kubernetes only when its operational benefits are part of the demonstration.

For a stronger hackathon story, prioritize one complete investigation → evidence → proposed correction → human approval → audit chain over adding more independent agents.
