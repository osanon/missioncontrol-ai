# Recommended next build sequence

1. Create the private GitHub repository, load the source into Codespaces, and validate the complete Docker + PostgreSQL deployment with the included disposable integration test configuration.
2. Configure a live model key and run the demo prompts against the real provider. Add token usage/cost accounting and narrative-to-evidence checks.
3. Add proposal revisions and reviewer identities. Keep uncertain corrections separate from automated execution; add typed correction forms with source evidence.
4. Add a dated multi-source staging layer with source IDs and reconciliation rules; keep source-of-truth and deduplication decisions explicit.
5. Integrate the verified Vultr Microsandbox/MCP execution layer. Keep writer credentials and approval execution outside the sandbox.
6. Deploy a private VM demonstration. Add streaming tool events and a saved investigation browser for judges.
7. Add exports/visual reports, background jobs, migrations, and observability. Consider Kubernetes only when its operational benefits are part of the demonstration.

For a stronger hackathon story, prioritize one complete investigation → evidence → proposed correction → human approval → audit chain over adding more independent agents.
