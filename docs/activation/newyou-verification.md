# DevCore slot verification record

This record describes the DevCore source prerequisite, not live activation or completed NewYou integration. WELL-145 is the source issue; WELL-147 is the separate NewYou integration/proof dependency. Plane and the exact PR retain current execution/CI/review state.

Source base is `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`. Implementation checkpoint is `189f2ad74613212b34b5fe9d0cd831f07cc57ca3`. Its executable SHA-256 is `27f5189f7fc27c5b462d8d342b8a97e01882b144ceebafe6cd1df232fad784f1`. Documentation-only commits may follow without changing that executable. The canonical source is `Carpe-Diem-Media/devcore-project`; the historical personal URL redirects there. This branch uses source version 1.2.0 and has no release tag.

The installed executable was inspected, not patched. It reports 1.1.0 with SHA-256 `df7dd3263197d33416b99699b5f09ee2b37bb4a45f55cc2a7bb4164dbbff9568`. No installation, live activation, database provisioning/drop, service change or agent migration occurred. Port 4237 remained occupied during read-only inspection. The initial legacy TEST/PLT holder PID 4026121 later released its lock without intervention by this work.

## Observed local checks

Commands ran from the isolated DevCore worktree rooted at `.worktrees/newyou-slots` unless a different directory is stated. Tool versions were Python 3.15.2, ShellCheck 0.11.0 and OCR 1.13.11. Linux headers confirm `PR_SET_CHILD_SUBREAPER` is 36; runtime tests exercise it.

- Baseline `python3 -m unittest discover -s tests -q` at source base ran 77 tests successfully, with two opt-in PostgreSQL integration skips.
- Focused red/green commands used `python3 -m unittest tests.test_slots -q` and individual named cases. They first failed for the missing allocator, administrative adapter and supervisor. Later regression cases failed for stdin loss, container-name SQL targeting, self-issued activation references, retained secret snapshots, discarded build overrides and missing heavy-capacity fencing/classification, then passed after their corresponding fixes.
- An early full working-candidate gate failed only `DevCoreBaselineTests.test_repository_owned_version_is_reported`, which still expected 1.1.0 after the intentional source version bump. The assertion was updated to the reviewed 1.2.0 source version. This was a changed-input correction, not an unchanged retry.
- After the catalog and directed contract fixes, `python3 -m unittest discover -s tests -v` ran 137 tests in 48.607 seconds and returned `OK (skipped=3)`. The three skips are the explicitly opt-in PostgreSQL integration tests. This means 134 executed tests passed locally, not that live SQL isolation was proved locally. The new slot module has 59 focused tests.
- `bash -n bin/devcore-project install/install.sh install/rollback.sh` passed.
- `shellcheck bin/devcore-project install/install.sh install/rollback.sh` passed.
- `git diff --check` and the staged equivalent passed. The complete staged implementation diff was inspected for scope, credentials, generated env files and destructive targets. All test credentials are synthetic.
- From `provenance/legacy-v1.0.0`, `sha256sum --check SHA256SUMS` passed. In a temporary archive extraction, `sha256sum --check SHA256SUMS.txt` passed, and the bundled executable matched `d30a90ba12c5394ec573ced1cdf80362c428280f7231c186ef7d05aa489adfd5`.
- An early syntax/lint batch was mistakenly invoked from the provenance directory and failed to find the relative source paths. Both checks were then rerun from the repository root and passed as recorded above.

The standard local command skips Docker integration. The existing hosted `postgres-integration` job runs `DEVCORE_RUN_POSTGRES_INTEGRATION=1 python3 -m unittest tests.test_postgres_integration -v` against only its own labelled disposable containers. The new scenario provisions two fresh generations concurrently, commits distinct synthetic markers, denies cross-slot connections and CREATEDB, releases one generation without changing the other, and proves a fresh reacquisition has no old table. Its hosted result must be checked against the exact final PR head. No local workstation database substitutes for this proof.

Hosted run `44051906490` at PR head `7f09b219293fc700bcb995de9478bc4dee6ca4f5` passed `checks` and failed the new PostgreSQL scenario during preparation. PostgreSQL serializes raw OID values as JSON strings, while the metadata verifier requires integers. The regression `PostgresAdapterTests.test_catalog_oids_have_numeric_json_types_at_postgres_boundary` reproduced that failure before explicit `bigint` casts fixed the SQL boundary. All six adapter tests and the full local suite then passed. This does not resolve hosted verification until a fresh run passes for the corrected head. The two existing integration scenarios passed in the failed run.

Corrected head `46f2f72656376a4f6a87606c1b3f2a8b7b3aa51f` passed both hosted jobs in run `44053367803`, including the real disposable PostgreSQL scenario. Independent review found no concrete safety blocker on that head. Subsequent directed changes clarify the partial-cleanup quarantine limit and explicitly reject managed `run all` before side effects. Its regression first failed for the generic argparse message, then passed after the explicit error. The executable changed, so final CI/OCR and independent review must use the newer candidate.

OCR was invoked as `ocr review --from origin/main --to HEAD` on implementation checkpoint `1e10975b518a1301a70839517e7938188f7acc7b` with comparison base `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`, after local gates passed. That original scan finished with four medium findings and one planning timeout. Independent review directed the partial-cleanup and all-profile contract/error corrections; dead-job and heavy-permit quarantine remain documented safety limits. A second scan covers `46f2f72656376a4f6a87606c1b3f2a8b7b3aa51f`; a refreshed scan must cover the corrected source checkpoint. The exact outcome, coverage, exclusions and any quota error belong in the PR's OCR Review Findings and Plane record. No OCR result is asserted here before it is observed. Native independent review must also inspect the exact final diff, head, authority and CI. Neither review authorizes merge or activation by itself.

## Directed OCR corrections

The `46f2f72656376a4f6a87606c1b3f2a8b7b3aa51f` scan finished with seven findings in 27m47s, session `d4f177ef-3263-4c6d-843e-a2a105edc7a2`. One planning request timed out and one context-compaction request was cancelled among 54 requests. The `4c0f1bcbf45ed5e69377c0c28ef3b069896289b2` scan finished with three findings in 19m30s, session `4addd66f-6716-4732-9c01-bf569647c5d9`. One planning request timed out among 36 requests. Both commands exited 0; this does not conceal their planning/coverage gaps. No quota error or provider change occurred.

Independent review confirmed nested mutable-environment trust and supplemental profile leakage as blockers in those earlier candidates. It directed environment rebuilding against verified job ownership/origin profile, active-profile supplemental injection, post-render DB alias rejection, setup-error retention, pre-launch capacity reuse and owned shutdown handling. The DEV TEST-binding finding was a false positive; the code already imported TEST values. Partial cleanup remains a documented quarantine limit. SIGTERM/INT now use verified descendant pidfds; SIGHUP deliberately detaches. Listener checks now run immediately and at most four times per second.

Focused regressions reproduced each corrected behavior before its fix. Additional source review found and closed legacy-declaration fallback under managed markers, partial marker acquisition, KeyboardInterrupt during environment preparation and missing kernel pidfd support. The stable local gate above covers these corrections. The source-linked capability map points to the corrected implementation checkpoint. New exact-head CI, OCR and independent review must reconcile the current candidate before handoff; their current outcomes belong in PR #6 and WELL-145. Earlier green CI never substitutes for the new head.

## Legacy connection boundary and latest directed corrections

The scan at `24185615e86123021bc204053877b9bba8fc6d1a` finished with three findings in 19m30s, session `185420ee-168f-447d-94e0-57aff5a0aa68`. It exited 0. One planning timeout and two context-compaction cancellations affected 3 of 31 requests; no quota error or provider change occurred. Independent review confirmed the medium legacy PUBLIC CONNECT issue and two low findings about unchanged-registry fsync during waits and console short writes.

At the current implementation checkpoint, provisioning checks effective PUBLIC CONNECT on exactly `new_you_test` before credentials or mutations. An explicit unsafe/unknown returned ACL value, including an absent database, raises a typed pre-mutation rejection and leaves the empty slot free for fresh preparation. SQL/endpoint exceptions remain quarantined. The distinction has a 21-attempt regression, so an unresolved prerequisite cannot consume the pool. Source does not change the legacy ACL. The [exact-target proposal](newyou-legacy-connect-proposal.md) remains NOT_AUTHORIZED and NOT_EXECUTED. The generation cleanup manifest does not authorize it.

Read-only status and exhausted wait passes no longer persist unchanged registry state. Console forwarding retries short writes; zero progress raises an output error while the private log is preserved. Focused tests failed before these changes and passed afterward. The final local command `python3 -m unittest discover -s tests -v` ran 144 tests in 47.417 seconds, with 141 executed passes and three opt-in PostgreSQL skips. `bash -n bin/devcore-project install/install.sh install/rollback.sh`, `shellcheck bin/devcore-project install/install.sh install/rollback.sh` and `git diff --check` passed for the corrected source. The new slot module has 64 tests.

Hosted `checks` and `postgres-integration` passed for `24185615e86123021bc204053877b9bba8fc6d1a` in run `44060843847`. Docs-only head `9db52272415921154cce21d98e8e8153fec7eed9` passed `checks` but failed `postgres-integration` in run `44061972314`. All three cases failed during admin bootstrap with psql exit 2; no slot assertion ran. The old fixture discarded stderr, and the pulled image digest was not recorded, so the specific failed-run trigger remains unknown. Independent investigation confirmed the socket-readiness race in the official PostgreSQL 18.6 Alpine entrypoint: its temporary socket-only server is stopped before final startup. The fixture now requires authenticated TCP SELECT 1 and records redacted failure stderr plus limited container state. Two regressions failed before that correction and passed afterward. The CI-owned SQL helper now asserts its requested successful statements, including the synthetic legacy setup. New exact-head CI/OCR and independent review remain required after these source changes.

Before the workstation metadata query, `mise exec -- devcore-project doctor` from the dirty NewYou worktree passed both DEV/TEST endpoint and owner authentication checks. The read-only query observed OID `4687800`, owner `new_you_test`, owner CONNECT true, PUBLIC CONNECT true, NOCREATEDB/NOSUPERUSER, zero memberships and no connected roles at that instant. No application table data was queried. The private mode-0600 receipt `/tmp/devcore-newyou-legacy-readonly-preflight.json` contains only target metadata, ACL and inspected container identity. Source `Postgres.check_endpoint` inspected the fixed TEST container and bound its immutable ID before `Postgres.execute` sent the catalog SELECT through stdin. No database, role, privilege, client, service or secret mutation occurred. This confirms the live activation prerequisite rather than granting permission to resolve it.

A fresh `git fetch origin` still resolved main to base `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`; `gh api user --jq .login` returned JC-Agents. `git status --short` in the dirty NewYou worktree showed the same WELL-144 files. `ss -Hltn '( sport >= 4220 and sport <= 4240 )'` showed the existing listener at 4237. `lslocks --noheadings --output PID,TYPE,MODE,PATH | rg 'newyou-shared-test-plt.lock'` found no current holder. These are observations at that checkpoint, not reservations or permission to reclaim anything.

## Port-conflict and URL-alias corrections

The scan at `da764b6abb4dd45c6883c1c99dfeeeed1aae3c2c` exited 0 after 25m22s with three findings across four selected files, session `ee2167de-9211-4e4a-9ec5-2bb8be1af650`. One planning timeout affected 1 of 45 requests, HTTP 200; no quota failure or provider switch occurred. Native independent review adjudicated the listener-address medium finding as conditional/non-blocking for the current NewYou configuration, the port-conflict medium finding as a confirmed correctness defect, and the URL-alias high finding as a medium source-boundary gap without evidence of current NewYou misrouting.

The supported NewYou config/dev.exs, config/test.exs and runtime.exs DEV path bind `127.0.0.1`. DevCore's process/port classifier does not enforce a bind address. The consumer contract now explicitly requires preserving and proving actual loopback locality, including port-0 helpers, before WELL-147 integration/activation. No source-level wildcard rejection or network sandbox is claimed.

Known pre-launch port conflicts now retain the idle allocation with a static diagnosis. Its owner can retry or release through the unchanged exact catalog/client guards without signaling the listener. Unknown post-launch foreign ownership still quarantines. Another command cannot change an existing active job through this path because retain rejects any active jobs. The new active-job regression failed against the prior committed module before passing against the correction.

After merging, the environment rejects PG*, names containing DATABASE_URL, bare DB_URL, names ending in _DB_URL and unknown DEV_DATABASE_/TEST_DATABASE_ keys. Only HOST, PORT, NAME, USERNAME and PASSWORD are supported under those prefixes. Template and inherited-alias regressions plus the prelaunch release regression first produced nine failing subcases, then passed after the correction. This is a supported-variable boundary, not evidence that current NewYou LocalConfig consumed those aliases.

At implementation checkpoint `189f2ad74613212b34b5fe9d0cd831f07cc57ca3`, `python3 -m unittest discover -s tests -v` passed 146 total in 49.447 seconds, with 143 executed passes and three opt-in PostgreSQL skips. The slot module has 66 tests. Bash syntax, ShellCheck, full diff whitespace and the source-linked hash checks passed. Exact previous head da764b6 passed both hosted jobs in run 44066522689, but that result is not copied to the corrected candidate. Fresh exact-head CI/OCR and native review are required. The legacy PUBLIC CONNECT activation prerequisite is unchanged and remains separately unauthorized.

## Reviewable installation and rollback commands

These commands are a proposed installation procedure for this exact source artifact. They have not run against the live workstation. Execute them only after independent source review and explicit owner installation authorization. If the reviewed source changes, recompute its checksum and use the newly approved artifact. Do not silently install a moving branch.

From the exact reviewed DevCore checkout:

```sh
git rev-parse HEAD
sha256sum bin/devcore-project
bash install/install.sh --source bin/devcore-project --version 1.2.0 --sha256 27f5189f7fc27c5b462d8d342b8a97e01882b144ceebafe6cd1df232fad784f1
~/.local/bin/devcore-project --version
sha256sum ~/.local/bin/devcore-project
```

A governed published release may replace this source-artifact route, using its approved release tag, source SHA and asset checksum. Do not claim that source version 1.2.0 is already published.

With separate rollback authorization, from the reviewed installer checkout:

```sh
bash install/rollback.sh
~/.local/bin/devcore-project --version
sha256sum ~/.local/bin/devcore-project
```

The existing installer keeps a sequenced previous executable. Rollback changes only the executable. It does not delete retained databases, metadata, logs or secrets. Before changing a live executable, let consenting managed jobs finish or preserve their reviewed execution version and nested verifier access. Follow the staged NewYou integration procedure before activation. The requested cleanup manifest SHA-256 is `2aef1ff43076759edea2dc5f32b00cf80499c9c573f1085e8cf898c5788fe3e7`; it remains `NOT_AUTHORIZED`.

## Acceptance assessment boundary

WELL-145 has eight source acceptance groups. Local evidence covers the 20-slot allocator, ownership/lifecycle, administrative guards, managed environment, negative/concurrency tests and integration documentation. Real PostgreSQL evidence is deferred to exact-head CI, and final independent review is still required. Source delivery is not installation, NewYou integration, shared-core PLT proof, the two-worktree NewYou business-fixture pilot, activation or resulting-main verification. Those are explicitly unverified under WELL-147 or the pending DevCore integration/release steps. Do not mark either issue Done from local checks alone.
