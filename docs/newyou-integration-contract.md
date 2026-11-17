# NewYou integration contract for managed slots

This is the DevCore-side consumer contract for WELL-147. It does not alter NewYou, complete its verification, or switch any running thread. DevCore source belongs in its own PR; NewYou changes belong in a separate NewYou PR. Keep WELL-144 and WELL-136 out of both diffs.

Reconnaissance used NewYou worktree `/home/jcschoeman96/.t3/worktrees/NewYou/t3-0463e245-481ee4cb6a05a062`. Its existing WELL-144 changes were preserved. Observed source was `a1d5d6c292c1e16c4cf4fd553182daccc194263e`; remote main was `6b92ba6d2b51be4f15af27c66a9d24dcf73640f8`. Recheck current main and all live dependencies before fresh implementation. The initial legacy lock holder was PID 4026121; later read-only inspection found no holder. Port 4237 remained occupied. Neither observation authorizes reclaiming a resource or using shared TEST without its existing coordination.

## Consumer opt-in

Preserve `.devcore/project.conf` legacy DEV/TEST allocations, role names, secret keys, `TEST_ROLE_CREATEDB=no` and `USE_REDIS=no`. Add `SLOT_POOL=.devcore/slots.json` using DevCore's exact declaration. Preserve `.devcore/render-map.tsv` and application variable naming. Managed snapshots use those templates; they do not replace worktree files while commands run. A test template must render the complete `TEST_DATABASE_HOST`, `PORT`, `NAME`, `USERNAME` and `PASSWORD` binding.

No slot may run against `new_you_test` or DEV as an isolation fallback. No application/test role receives CREATEDB. Do not use Ecto partitioning. Keep port 4220 outside the pool; managed port validation extends through 4240. Existing listeners block their numbers until their owners stop or consent to adoption. There is no process-killing adoption command.

The normal entry points remain:

```sh
mise exec -- devcore-project run test -- mix test PATH
mise exec -- devcore-project run test -- mix check
mise exec -- devcore-project run test -- mix check.deep
mise exec -- devcore-project run dev -- mix phx.server
```

Current `mix.exs` already runs `ecto.migrate --quiet` before tests and does not require TEST CREATEDB. Confirm the current aliases again. A fresh generation is empty, so every first run must use the current branch's migrations. A failed migration must retain its diagnosis and allocation. Do not clone shared/retained data, share stale schemas between branches, or bypass owning Ash interfaces for synthetic business fixtures.

## Fail-closed runtime validation

`lib/new_you/local_config.ex` currently accepts only `new_you_dev` and `new_you_test`. Keep the legacy validation where deliberately supported. Managed mode must be selected explicitly by the job markers, and every partial, stale or malformed marker must fail rather than falling back to legacy.

DevCore injects non-secret `DEVCORE_SLOT_PROJECT`, `DEVCORE_SLOT_LEASE`, `DEVCORE_SLOT_GENERATION`, `DEVCORE_SLOT_JOB`, `DEVCORE_SLOT_WORKTREE` and `NEW_YOU_PORT`. It supplies generation-specific TEST values through the existing renderer. A name prefix or marker string is insufficient evidence of ownership. From the active child process, call:

```sh
devcore-project slots verify --lease LEASE --generation GENERATION --job JOB
```

The verifier checks private registry ownership, exact generation, canonical current worktree, `in_use` state, a live supervisor's boot/PID/start identity and membership in its managed descendant tree. It also reports the registered originating DEV/TEST profile. Nested calls rebuild and verify the allocation rather than trusting mutable child database variables; TEST-origin jobs cannot escalate to DEV. Partial markers or a substituted non-opt-in declaration must fail closed. It returns only the expected project, slot, port, database, role and identifiers. Compare all supplied runtime TEST values against that result plus fixed `127.0.0.1:55433`; require a password without exposing it. Reject mixed legacy/managed identities, changed hosts/ports/users/database names and `MIX_TEST_PARTITION`. Keep production's separate configuration path and existing production safeguards intact. A forged environment alone must not make an unrelated process eligible.

`config/runtime.exs` currently uses LocalConfig for DEV and TEST. Update its worktree/port seam without broad DATABASE_URL acceptance. `test/support/proof/result.ex` has an independent database identity check; update it to the same verified contract rather than adding a second permissive rule. Public LocalConfig functions need appropriate documentation/specs and focused failure tests under NewYou's conventions.

## Child-process coverage

Audit actual environment inheritance; Elixir ports normally inherit the environment unless overridden, but a proof must establish the final endpoint rather than assume it. Include regular ExUnit, migration commands, HTTP/browser startup, restart helpers and production-mode probes. A production-mode test probe remains a test allocation, not production configuration authority.

Inspect at least these current seams:

- `test/support/proof/p8_05_browser.ex` and `test/proof/p8_05_browser.mjs` for Port.open and Node/browser children.
- `test/support/proof/p8_09.ex`, `p8_11.ex`, `p8_12.ex`, `p8_13.ex`, `p8_15.ex`, `email_change_scenarios.ex`, `delivery_recovery_scenarios.ex` and `reconciliation_scenarios.ex` for restart/child BEAM launchers.
- `test/proof/self_test.exs` for prod-mode compilation/probes and build overrides.
- `test/support/entry_journey.ex` and the browser helper for safe port-0 temporary servers.

Assert actual database/role/endpoint identity in child paths, not only marker propagation. Nested compatible DevCore calls reuse the active job. Preserve helper port 0 instead of consuming a second fixed slot. Audit intentional committed writes outside Sandbox rollback and teardown attribution. Do not clean another fixture's rows or treat a retained shared database as disposable.

The Linux supervisor requires child-subreaper and pidfd support and covers all descendants until they exit, even after launcher loss. SIGHUP detaches; SIGINT/TERM stop only verified owned descendants while supervision continues. An abnormal supervisor loss quarantines resources; it does not terminate survivors. Do not modify active agents to adopt the allocator. Only consenting new sessions switch.

## Worktree builds and PLTs

DevCore validates mutable build/dependency paths and supplies worktree-local `_build` and `deps`. Inspect existing overrides and symlinks before relying on them. This does not make simultaneous compilation into one worktree safe. Consumer wrappers must coordinate mutable worktree builds while permitting independent worktrees and focused database tests.

Current `mix.exs` puts project PLTs in `_build/plts` and local core PLTs in `Mix.Utils.mix_home()`. CI uses `_build/plts`. Installed Dialyxir's `lib/dialyxir/plt.ex` can add/remove entries in a prepared core PLT, including worktree consolidation paths. Therefore an existence check or a lock around only a named cold-preparation command is insufficient proof of safe shared reads.

The NewYou PR must implement automatic, cache-specific synchronization for all mutable shared-core work, then release that lock before database suites or independent analysis. Prefer a prepared, toolchain-keyed core cache copied into each worktree for any Dialyxir operation that may refresh it. Include pinned OTP/Elixir, architecture, Dialyxir version, relevant configuration and consolidation inputs in identity decisions. Do not copy or mutate an existing active shared PLT merely to collect proof. No shared TEST lease is a PLT lock. Preserve CI's existing cache behavior unless a necessary reviewed change is documented. WELL-135 remains separate cold-build research.

## Required application proof and gates

Use two independent, consenting worktrees and fresh allocator-owned generations. Apply each branch's migrations, create distinguishable synthetic records through approved business interfaces, and demonstrate that each process sees only its own rows. Prove a cross-slot runtime connection is denied. Verify child BEAM/browser/restart/prod-probe paths against the actual database identity. Include a deliberately failing run, retained logs and an unavailable retained database, followed by exact release and fresh reacquisition with no previous fixture rows. A successful test exit alone is insufficient.

Prove cache preparation serializes automatically and independent analysis proceeds after preparation without holding TEST or shared core mutation locks. Measure full-suite/build memory and throughput before selecting the activation concurrency policy. The current DevCore cap of two is provisional; 20 slots do not imply 20 full suites.

Run NewYou's unchanged `mix check` and required `mix check.deep`, exact-head Foundation Smoke/Application CI/Hex routing, capability-map checks and code-change-verification/OCR checkpoint. Preserve every failed command, exclusion and quota error. Do not change providers to bypass a quota. Generate the required source-linked capability map and PR history, obtain independent Master Gate review, and reconcile resulting main before Done. NewYou authority routers remain read-only for these ordinary tooling decisions.

## Staged activation and rollback

1. Review and integrate DevCore source through its own PR and resulting-main checks. Publish/install a verified release only with separate authorization. Record the source SHA, release tag/checksum, installed checksum and reported version independently. Version 1.2.0 in this branch is an unreleased source version.
2. Review and integrate the NewYou consumer PR separately. Keep legacy coordination instructions until the replacement is activated and proven. Recheck current main, active lock ownership, all ports 4221..4240 and reserved port 4220. Do not stop an occupant to make the range pass.
3. From NewYou, generate `devcore-project slots manifest`. Compare it byte-for-byte with the reviewed bounded contract and record its digest. The owner approves its exact `approval_text`; then run `slots enable --manifest DIGEST --approval-ref OWNER_COMMENT_URL`. This is the one initial authorization for routine registered-generation creation/cleanup, not permission to reset shared TEST.
4. Run a consenting two-worktree pilot, preserve failure/retain/reuse and child/PLT evidence, then enable normal automatic entry points. Record exact activation commands and results. No existing thread is switched automatically.
5. To stop new acquisitions, run `devcore-project slots disable`. Existing jobs retain their resources. Let owned jobs finish, inspect `slots status`, and release only exact idle lease/generation pairs from their owning worktrees. Do not remove the declaration while managed jobs still need nested verification.
6. Once no active managed jobs remain, revert the NewYou opt-in through review if rollback is needed. A verified DevCore rollback uses the existing installer rollback procedure under separate installation authority. Retained/quarantined databases and records survive rollback. Their cleanup still requires the original exact target guards or a new explicit reconciliation authorization. Legacy shared TEST users keep their existing lock.

No activation, cleanup, live installation, active-agent migration or resulting-main proof is claimed by this document.
