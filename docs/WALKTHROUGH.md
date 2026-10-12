# Five-minute walkthrough

**0:00–0:45 — problem and boundary.** A client can time out after submission and retry. A worker can die after claiming. We need durable history and safe retries. The demo computes a square, not a payment or shell command. Show the API and worker terminals and the dashboard.

**0:45–1:30 — duplicate submission.** Submit key `walkthrough-1`, value 12. Repeat unchanged: same job ID. Change value: conflict. Explain that the database's unique key and the serialized transaction, not a client cache, arbitrate concurrency.

**1:30–2:30 — failure and retry.** Submit a fresh key with “Fail twice, then succeed.” Show two transient attempts, then one committed result 144. Backoff is 1 then 2 seconds. Show permanent failure stopping after one attempt and exhaustion stopping after three. Retry count means total attempts, including crashes.

**2:30–3:30 — real crash demonstration.** Run `python -m unittest -v`. Point to the two real subprocess crash tests: one kills a claimed worker before effect commit; recovery waits for lease expiry, then commits once. The other kills it after effect and success commit; a new worker finds no eligible job. Stale token test rejects an expired worker. Tests use short leases and advance retry due timestamps to keep the demonstration quick; application backoff remains unchanged.

**3:30–4:30 — transaction reasoning.** Draw API → jobs/attempts → worker → effects. Claims and results use separate transactions. The commit checks ownership and lease. Effect and success share a transaction. If a process dies in a transaction SQLite rolls it back; if after commit, both survive. The guarantee covers committed local effects. External effects require receiver-side deduplication or reconciliation. Never call this exactly-once execution.

**4:30–5:00 — limits and ownership.** This is a local single-host learning project with no heartbeat, authentication, production deployment or scaling claim. Explain test coverage, monthly checks, and AI assistance. State the next improvement only if asked: lease renewal for longer work or pagination for larger histories.

## Unaided checkpoint (owner completes; not yet claimed completed)

Close AI tools and explain in your own words:

1. Why can two API requests produce only one job, and why does a changed payload fail?
2. Why does a claim require a transaction? What does the fencing token protect?
3. Enumerate crashes before claim commit, after claim, during effect commit, and after effect commit.
4. Why cannot SQLite guarantee exactly-once email delivery?
5. Show how to reproduce a test failure and locate the persisted attempt.

Then implement a small validation change and its test without assistance, run tests, and explain the diff. Record the actual date and outcome privately or in a future project note; do not claim this checkpoint is done today.
