# Cloud development costs and temporary substitutions

Checked October 5, 2026. Start with GitHub Codespaces and the no-key guided demo; Vultr is a later expense.

## GitHub Codespaces

GitHub's published personal-account allowances and excess-usage rates:

| Item | Allowance or price |
|---|---:|
| GitHub Free | 120 core-hours/month; 15 GB-month storage |
| GitHub Pro | 180 core-hours/month; 20 GB-month storage |
| 2-core compute above allowance | $0.18 per running hour |
| 4-core compute above allowance | $0.36 per running hour |
| Storage above allowance | $0.07 per GB-month |

At 2 cores, 120 core-hours equals approximately 60 running hours; at 4 cores, 30 hours. Usage is shared across your Codespaces. For example, 80 hours on a 2-core machine uses 160 core-hours: with an otherwise-unused Free allowance, the excess compute would be about $3.60, plus any excess storage.

Stop the Codespace to stop compute; storage still accrues while it exists. Docker images and development data consume storage. Organization accounts do not include the personal free quota. Review actual billing ownership, usage, payment settings, and budgets before enabling paid usage.

Source: https://docs.github.com/en/billing/concepts/product-billing/github-codespaces

## Inference and later hosting

| Setup | Planning cost | Notes |
|---|---:|---|
| Guided demo in Codespaces | $0 inference; Codespaces usage as above | No provider key or model API requests required. |
| Live GPT-5.4 mini | $0.75/M input + $4.50/M output tokens | Provider charges are separate from Codespaces. |
| Temporary model testing budget | Suggested $5–$15 allocation | Planning target, not an app-enforced dollar cap. |
| Later Vultr VM | Reserve $20–$50/month as a planning allowance | Confirm the actual region/plan, storage, backup, and transfer prices before purchase. |
| Microsandbox host | Not priced in this bundle | Verify virtualization requirements and current plan pricing first. |

A complete investigation using 20,000 input and 3,000 output tokens would be approximately $0.0285 at those model rates. This is illustrative: repeated context, evidence, and reasoning can increase usage. The app limits steps and output tokens but does not yet track dollar spend.

Temporary substitutions:

- Use the guided demo while API access or credits are pending.
- Run PostgreSQL inside the Codespace's Docker stack before purchasing managed database hosting.
- Use an inference API before considering a GPU server.
- Keep bounded SQL tools for the core demo while developing the separate Microsandbox adapter; SQL role enforcement is not microVM isolation.

Model source: https://developers.openai.com/api/docs/models/gpt-5.4-mini
Cloud pricing to verify before deployment: https://www.vultr.com/pricing/
