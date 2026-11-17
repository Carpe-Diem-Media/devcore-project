# DevCore slot verification record

This record describes the DevCore source prerequisite, not live activation or completed NewYou integration. WELL-145 is the source issue; WELL-147 is the separate NewYou integration/proof dependency. Plane and the exact PR retain current execution/CI/review state.

Source base is `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`. Implementation checkpoint is `a5caa029a4bf4049ec6d5f51d4df15d07d23dee3`. Its executable SHA-256 is `e76cb9206d6e00226ab9549bfa2a342c4da867f2a7d21956240035b1bf65d93a`. Documentation-only commits may follow without changing that executable. The canonical source is `Carpe-Diem-Media/devcore-project`; the historical personal URL redirects there. This branch uses source version 1.2.0 and has no release tag.

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

## Administrative database ownership correction

Full `ocr review --from origin/main --to HEAD` at `bca4adc20fabee9eb5b05991c62c6ea4c1145828` exited 0 after 21m57s, session `bc53e04e-0b0c-4ee3-94b8-b0612ad4a877`. It selected four of 19 changed paths with 15 configured exclusions. One planning timeout affected 1 of 48 requests, HTTP 200; no quota error or provider change occurred. The medium listener-address finding has the existing conditional consumer disposition. Independent review confirmed a new HIGH blocker: a runtime database owner can grant CONNECT to PUBLIC or another role, reopening cross-slot access despite initial revocation. Earlier green CI did not test this operation and does not certify that candidate's isolation boundary.

Two focused regressions failed before correction. The current source keeps database ownership with the existing `devcore_admin`. Runtime gets only CONNECT/TEMPORARY on its database and USAGE/CREATE on public, without grant options, database CREATE, ownership or role memberships. Catalog verification requires the administrator owner OID, rejects runtime ownership and any runtime-owned database, records the owner OID at preparation and compares it during cleanup. An additional test rejects a changed administrator identity before mutations. The exact declaration and manifest now bind `database_owner`; no old manifest approval can authorize this changed contract. No approval has been granted for either manifest.

New CI-owned assertions inspect unchanged ACL after attempted GRANT to PUBLIC and the other slot role, recheck denied cross-slot access, deny SET ROLE and ALTER DATABASE ownership, and exercise transactional table/function/index/temporary-table DDL. Current NewYou migrations were inspected read-only and use public-schema application objects and Ash functions; no current CREATE EXTENSION/SCHEMA or ALTER DATABASE requirement was found. This is compatibility evidence for the scoped grants, not execution of branch migrations. See PostgreSQL's [GRANT documentation](https://www.postgresql.org/docs/18/sql-grant.html) and [privilege inquiry functions](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-INFO-ACCESS-TABLE).

`python3 -m unittest discover -s tests -v` at the corrected implementation ran 149 tests in 49.900 seconds, with 146 executed passes and three opt-in PostgreSQL skips. There are 69 slot tests. Bash syntax, ShellCheck and diff whitespace checks passed. The exact previous head bca4adc passed both jobs in run 44072541031, but that result predates this security correction. Fresh exact-head CI, full OCR and native independent review remain required for the corrected candidate. The live legacy PUBLIC CONNECT prerequisite and separate installation/cleanup authority are unchanged.

## Partition setting after environment merge

Full `ocr review --from origin/main --to HEAD` at `348e95789e51315076f7478b06fc27453feef8d7` exited 0 after 19m29s, session `c769731b-7d73-4b0b-a0bb-404f4e1f5274`. It selected four of 19 changed paths, with the same 15 configured exclusions. One planning timeout affected 1 of 36 requests, HTTP 200; no quota error or provider change occurred. One medium finding at bin/devcore-project:2257-2258 identified rendered MIX_TEST_PARTITION bypassing the inherited-environment check. Native independent review confirmed the source-contract gap. Current NewYou LocalConfig rejects nonempty partition values, so present application misrouting was not demonstrated.

Two focused regression tests produced four failing cases before correction, covering both DEV/TEST templates and supplemental all-profile bindings. The final merged environment now rejects a nonempty MIX_TEST_PARTITION after all bindings, before any managed child launch. The tests pass and verify private snapshots are removed after rejection. Empty values retain the existing non-partition behavior. The database ownership manifest/digest is unchanged.

At this corrected implementation, `python3 -m unittest discover -s tests -v` passed 151 total in 50.487 seconds, with 148 executed passes and three opt-in SQL skips. There are 71 slot tests. Bash syntax, ShellCheck and diff whitespace checks passed. Exact prior head 348e957 passed both hosted jobs in run 44077006348, including the administrative ownership proof, but that result does not certify this source change. Fresh exact-head CI, full OCR and native review remain required. No live installation, activation, ACL change or NewYou modification occurred.

## Final DEV binding validation and review limits

Full `ocr review --from origin/main --to HEAD` at `06f6493af9a004874c2cce673f57e56f4d8fd5d8` exited 0 after 15m16s, session `bde97762-fae7-45c6-bb26-710113680a8e`. It selected four of 19 paths, with the same 15 configured exclusions. No tool/LLM retry error was reported; no quota failure or provider change occurred. Four medium findings concerned protected DEV access, listener locality, signal snapshots and final DEV environment bindings.

Native independent technical review found no cross-cluster access path: DEV and TEST are separate containers/clusters and the generated LOGIN exists only on TEST. The CI-owned scenario now additionally verifies the role is absent on the separate DEV cluster and cannot authenticate there. The listener-address finding remains the documented WELL-147 consumer gate. Signal handling sends a verified snapshot without forced escalation; signal-resistant or later descendants keep their resources. Documentation now states this limit without promising bounded termination. These are preliminary technical dispositions, not owner Master Gate approval.

The DEV binding finding was confirmed. Two focused regressions reproduced 11 failing cases for omitted or changed DEV host, port, name, user and password, plus supplemental override. The correction checks final DEV-profile bindings against the fixed endpoint, unchanged project identity and canonical secret. TEST still excludes DEV bindings. All cases pass and snapshot cleanup is asserted. No new ACL scan/change, forced kill or credential rotation was added.

An initial full gate ran 153 tests in 61.908 seconds with 150 executed passes and three SQL skips. After adding the separate-DEV-cluster negative CI assertion, the stable `python3 -m unittest discover -s tests -v` gate ran 153 in 57.165 seconds, again 150 executed passes and three opt-in SQL skips. There are 73 slot tests. Bash syntax, ShellCheck and full diff whitespace passed. Prior head 06f6493 passed both hosted jobs in run 44080515661; fresh CI/full OCR/native review must cover the corrected candidate. The exact manifest remains unchanged and unapproved. No workstation installation, activation, database/privilege change, NewYou edit or agent interruption occurred.

## Reviewable installation and rollback commands

These commands are a proposed installation procedure for this exact source artifact. They have not run against the live workstation. Execute them only after independent source review and explicit owner installation authorization. If the reviewed source changes, recompute its checksum and use the newly approved artifact. Do not silently install a moving branch.

From the exact reviewed DevCore checkout:

```sh
git rev-parse HEAD
sha256sum bin/devcore-project
bash install/install.sh --source bin/devcore-project --version 1.2.0 --sha256 e76cb9206d6e00226ab9549bfa2a342c4da867f2a7d21956240035b1bf65d93a
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

The existing installer keeps a sequenced previous executable. Rollback changes only the executable. It does not delete retained databases, metadata, logs or secrets. Before changing a live executable, let consenting managed jobs finish or preserve their reviewed execution version and nested verifier access. Follow the staged NewYou integration procedure before activation. The requested cleanup manifest SHA-256 is `3fb71d0ed24dfc4ab8ef75226916da624f5ca4a18343695a154733eb2a93e556`; it remains `NOT_AUTHORIZED`.

## Acceptance assessment boundary

WELL-145 has eight source acceptance groups. Local evidence covers the 20-slot allocator, ownership/lifecycle, administrative guards, managed environment, negative/concurrency tests and integration documentation. Real PostgreSQL evidence is deferred to exact-head CI, and final independent review is still required. Source delivery is not installation, NewYou integration, shared-core PLT proof, the two-worktree NewYou business-fixture pilot, activation or resulting-main verification. Those are explicitly unverified under WELL-147 or the pending DevCore integration/release steps. Do not mark either issue Done from local checks alone.
