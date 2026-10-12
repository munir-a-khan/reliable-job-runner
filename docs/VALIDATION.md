# Validation evidence

Checked on Windows with Python 3.13, October 12, 2026.

`python -m unittest -v`: **10 tests, 1.897 seconds, OK**.

Coverage: concurrent duplicate requests (16 calls, 8 threads); payload conflict and validation; competing claims; transient failures then success; permanent failure; retry exhaustion and backoff eligibility; stale worker fencing; crash consuming final attempt budget; real worker killed before commit and recovered; real worker killed after commit without another committed effect. Tests use temporary databases and actual subprocess termination for crash checks.

`python qa_demo.py`: HTTP end-to-end **PASS** for creation, duplicate, conflict, worker execution, transient retries, exhaustion and permanent failure. Headless dashboard **PASS** for rendering, browser submission, refresh and no JavaScript errors. Uses only synthetic jobs. The desktop and mobile screenshots were actually rendered and visually inspected; mobile table overflow was corrected before recapture.

![Synthetic desktop dashboard](dashboard.png)

[Mobile screenshot](dashboard-mobile.png)

Environment notes: initial sandbox runs could not access its default temporary directory or localhost sockets. Tests now create temporary directories inside the repository. HTTP/browser QA succeeded outside the socket-restricted sandbox. An inherited `SSLKEYLOGFILE` pointed outside the workspace; it was removed only from the QA shell's process environment, not from machine settings. Python emitted a runtime-location warning inside the sandbox but completed the tests. No existing Chrome application was used or altered.

Independent Claude CLI review was requested with read-only project scope. Status is pending; no completed review or findings are claimed yet. Manual review verified claim serialization, lease/token fencing, transaction boundaries, bounded inputs and text-only dashboard rendering. No CI is configured; no CI result is claimed.

Limits: no power-loss/disk-corruption simulation, multi-host test, sustained load test, long-job heartbeat, external effect integration or unaided owner checkpoint. Test results establish the bounded synthetic demo's behavior, not production readiness.
