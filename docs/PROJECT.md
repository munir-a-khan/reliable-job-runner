# Scope, requirement mapping and maintenance

Bounded seven-day plan: day 1 working API/database/worker; days 2–3 reliability tests and first runnable milestone; days 4–5 independent review and dashboard QA; days 6–7 walkthrough practice and final verification. Work is accelerated when checks finish; no artificial waiting. No cloud deployment, paid services, real customer data or generalized job execution.

| Target requirement | Demo evidence | Honest boundary |
|---|---|---|
| Amazon Leo: Python, maintainable code, database and version control experience | Standard-library implementation, SQL transactions, Git history | Learning project; no claim of cloud or distributed scale |
| Amazon Leo: resilient systems, troubleshooting, technical documentation | Lease recovery, persisted attempts, failure injection, walkthrough | Local simulation; no production operations experience claim |
| Amazon Leo: AI development tools and code review | AI-assisted disclosure and independent review record | Owner must pass unaided explanation checkpoint |
| Sacramento Applications Analyst: design, testing, database integrity | Explicit states, schema, concurrent tests and atomic effects | Does not replace degree/paid-experience qualifications |
| Sacramento: troubleshooting, documentation and training | Failure history, Windows instructions, five-minute explanation | No County system access or endorsement |

Sources checked October 12, 2026: [Amazon job 10513110](https://amazon.jobs/en/jobs/10513110/software-development-engineer-amazon-leo-early-career-2026), [Sacramento job 29609-A](https://www.governmentjobs.com/careers/sacramento/jobs/newprint/2373671). County posting lists the December 18, 2026 filing cutoff at 5 pm; use the official posting/application portal for filing instructions. Project evidence is separate from application eligibility. No private resume or employment evidence is stored here.

## Monthly maintenance (about 15 minutes)

- Run `python -m unittest -v` on the current Python runtime and review any failures.
- Start the two terminals, submit an immediate and transient job, inspect history.
- Check database size and disk space; archive only disposable synthetic histories. Stop both processes before copying the database (or use SQLite's backup API); never copy only the main file during active WAL writes.
- Run `PRAGMA integrity_check` on a backup and practice restoring it to a separate path.
- Review Python security updates, repository visibility and tracked files for unintended data.
- Revisit the documented limits before changing the workload, host or exposure.

No scheduled automation or paid CI has been enabled.
