# Five-minute demo

Use the default July–September 2026 reporting period and a freshly seeded database. Start in demo mode for a repeatable walkthrough.

1. **Ask MissionControl:** click Quarterly briefing. The app invokes real metric tools, compares the prior calendar quarter, and displays the evidence. Explain that this guided mode is deterministic; use live mode for open-ended investigation.
2. **Inspect the answer:** 581 distinct people served, 321 job records, $18.58 average valid starting wage, and 104 stable exits out of 184 (56.5%). Expand the tool trace. Export the evidence report.
3. **Connect programs:** choose the employment/housing comparison. Combined cohort: 188 of 290 (64.8%); employment only: 111 of 291 (38.1%). Discuss the denominator and the fact that these are associations, not causal effects.
4. **Find issues:** Data Health begins with 56 findings: 12 possible duplicates, 10 reversed enrollment dates, 10 missing exit dates, 8 implausible wages, and 6 negative service records.
5. **Control a change:** inspect employment record #1. Propose clearing its 1500 wage and adding a review flag. Show the exact before/after values. Add the reviewer token, approve, then show the audit entry. The wage finding disappears; the preserved audit records the old value.
6. **Close on trust:** explain the read-only SQL account, bounded tools, approval boundary, and roadmap to sandbox execution.

Suggested live-mode prompts:

- How did stable housing exit rates change from Q2 to Q3 2026? Show numerators and denominators.
- Break housing exits down by month and destination. What can and cannot explain the difference?
- How many people receiving employment and housing services obtained jobs, compared with employment-only recipients?
- Identify questionable wage records and propose a review action for one. Do not apply it.

Do not describe the code as deployed to Vultr or running in Microsandbox until that integration has actually been completed and verified.
