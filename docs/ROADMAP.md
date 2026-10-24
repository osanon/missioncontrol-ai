# Recommended next build sequence

## Agent-first plan (current)

The target: AI agents find issues, propose corrections and review each other's proposals; people only approve, reject, or send back.

1. **Foundations (done; see PHASE1_UPDATE.md):** personal reviewer identities, send back for reevaluation, proposal provenance, reliable live runs, Alembic migrations.
2. **AI reviewer agent and approval queue (done; see PHASE2_UPDATE.md):** an independent reviewer agent (its only write tool is `submit_review`) checks proposals; the queue puts disagreements first. Runs on demand; phase 3 chains it automatically after proposals.
3. **"Perform health check" button and worker:** the SQL scan stays free; AI work runs only when a person starts it. Runs are recorded with token use and cost, skip findings already handled, stop at a token limit, and can be cancelled. Sent-back items are re-proposed immediately.
4. **"Live health checks" toggle:** an opt-in schedule with a daily token budget, off by default.
5. **Evidence sources and evaluation:** connect the sources agents may cite (for example payroll or case-management exports) and measure proposal precision against the planted anomalies.

## Earlier sequence

1. Create the private GitHub repository, load the source into Codespaces, and validate the complete Docker + PostgreSQL deployment with the included disposable integration test configuration.
2. Configure a live model key and run the demo prompts against the real provider. Add token usage/cost accounting and narrative-to-evidence checks.
3. Add proposal revisions and reviewer identities. Keep uncertain corrections separate from automated execution; add typed correction forms with source evidence.
4. Add a dated multi-source staging layer with source IDs and reconciliation rules; keep source-of-truth and deduplication decisions explicit.
5. Integrate the verified Vultr Microsandbox/MCP execution layer. Keep writer credentials and approval execution outside the sandbox.
6. Deploy a private VM demonstration. Add streaming tool events and a saved investigation browser for judges.
7. Add exports/visual reports, background jobs, migrations, and observability. Consider Kubernetes only when its operational benefits are part of the demonstration.

For a stronger hackathon story, prioritize one complete investigation → evidence → proposed correction → human approval → audit chain over adding more independent agents.
