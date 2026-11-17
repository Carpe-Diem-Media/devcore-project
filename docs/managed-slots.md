# Managed NewYou slots

DevCore 1.2.0 adds an opt-in NewYou allocation contract. This is source capability, not workstation activation or completed NewYou integration. WELL-145 owns this DevCore prerequisite. WELL-147 owns the separate NewYou consumer changes and application/PLT proof. No existing NewYou declaration is changed by this repository.

The pool has exactly 20 slots. Slot 01 uses HTTP port 4221 and slot 20 uses 4240. The primary-checkout port 4220 is outside the pool. Each lease has a random lease ID and a different random generation, both 32 lowercase hexadecimal characters. A slot receives database `dc_new_you_sNN_gGENERATION` and role `dc_new_you_sNN_gGENERATION_r`. Reuse always creates a new generation and empty database from `template0`.

Only TEST is isolated. All DEV jobs continue to use `127.0.0.1:55432/new_you_dev`. Concurrent writes to shared DEV still require coordination. DEV and TEST are separate PostgreSQL clusters. Managed LOGIN roles are created only on TEST. The existing `new_you_test` allocation remains intact for cooperating legacy users. Redis stays disabled.

## Opt-in and authority

The future NewYou PR adds `SLOT_POOL=.devcore/slots.json` to its existing project declaration and commits the exact [pool declaration](examples/newyou-slot-pool.json). It preserves both legacy owner allocations and `TEST_ROLE_CREATEDB=no`. Other v1 consumers retain their existing behavior. A declaration alone does not enable provisioning or cleanup.

`devcore-project slots manifest` reports the full non-secret bounded contract, its SHA-256, current HTTP conflicts, host capacity and required approval text. The digest binds the canonical registry directory, project, TEST endpoint, all 20 slot definitions, protected databases and cleanup rule. The prepared [workstation target manifest](activation/newyou-workstation-manifest.json) records the requested target before installation. It grants no authority.

After source review and separately authorized installation, the owner posts the exact `approval_text` as a comment on this repository's PR or issue. The tool verifies that GitHub reports `JCSchoeman96` as its author, that the comment belongs to this repository and URL, and that its entire body matches the exact manifest digest and cleanup statement. JC-Agents cannot issue that approval. `slots enable --manifest DIGEST --approval-ref COMMENT_URL` then records the verified non-secret receipt locally. It does not create or delete a database.

Approval covers only future allocator-created generations satisfying every recorded guard. It never covers legacy, retained shared, production, unrelated or merely similarly named databases. The local receipt avoids a network or owner round trip for routine leases. Agents must not invoke enable before the owner actually grants the bounded authorization. A changed manifest requires new approval. Source review, merge authority, installation authority and cleanup authority are distinct.

Activation also requires a safe legacy connection boundary. Before creating a role or generating its password, provisioning reads the effective `PUBLIC CONNECT` ACL of exactly `new_you_test`. Default or explicit PUBLIC CONNECT, a missing database or an unknown returned value blocks preparation without changing privileges. This typed rejection proves no resources were created, so the empty slot returns to `free` and must pass fresh preparation on its next claim. SQL/endpoint exceptions and uncertain preparation still quarantine. PostgreSQL has no per-role DENY that overrides PUBLIC. Read-only workstation checks on 2026-11-17 confirmed the legacy allocation permits PUBLIC CONNECT; no privileges were changed. The [separate connection-boundary proposal](activation/newyou-legacy-connect-proposal.md) requires owner authorization before implementation or execution. The disposable cleanup approval does not authorize that proposal.

## Normal commands after integration and activation

All NewYou Elixir/Mix commands retain Mise outside DevCore:

```sh
mise exec -- devcore-project run test -- mix test test/new_you/local_config_test.exs
mise exec -- devcore-project run test -- mix check
mise exec -- devcore-project run test -- mix check.deep
mise exec -- devcore-project run dev -- mix phx.server
```

Managed mode supports `run dev` and `run test`. It rejects `run all` before acquisition because combining legacy profiles could restore shared TEST credentials. Projects without `SLOT_POOL` keep their existing `run all` behavior.

With `SLOT_POOL` enabled, an ordinary `run` acquires a slot, provisions its fresh TEST generation, builds a command-local environment, supervises its children, then releases on success. A failed command or environment preparation retains the database and diagnosis. Operational renderer timeouts never leave an unpublished automatic lease ready. There is no shared TEST fallback. Twenty occupied, retained, quarantined or externally blocked slots produce an explicit exhausted error. `slots acquire --wait SECONDS` supports a bounded wait up to 3600 seconds; interruption cancels the waiter without acquiring a slot. The default is immediate exhaustion.

Explicit session control uses non-secret identifiers printed by acquisition and status:

```sh
devcore-project slots acquire --wait 30
devcore-project slots status
mise exec -- devcore-project slots run --lease LEASE --generation GENERATION test -- mix test
# Explicit sessions remain leased until release.
devcore-project slots retain --lease LEASE --generation GENERATION
devcore-project slots release --lease LEASE --generation GENERATION
```

Run options precede the profile because the remainder after the profile is the child command. `slots run --retain test -- COMMAND` retains successful output for diagnosis. `slots run --heavy test -- COMMAND` selects the separate heavy gate for compound/custom commands. Plain `mix check`, `mix check.deep`, `mix compile` and `mix dialyzer` select that gate automatically. Full `mix test` without focused targets also uses the heavy gate. Focused tests use independent leases without this gate.

A session permits one managed command at a time. Separate commands in the same worktree acquire separate TEST generations and never rewrite each other's environment files. Nested compatible `devcore-project run test` calls within a live job reuse that allocation after rebuilding its verified environment. The registry stores the originating DEV/TEST profile; mutable child environment values cannot turn a TEST job into a shared DEV job. Partial identity markers or a substituted legacy declaration fail before fallback or acquisition. Keep `_build`, dependencies and project PLTs local to each worktree; concurrent commands that mutate the same worktree build still need the build/cache rules in the [NewYou integration contract](newyou-integration-contract.md).

## Lifecycle and process ownership

A slot starts absent or `free`. Acquisition atomically records `preparing` under a private cross-process flock before any administrative work. Successful preparation records database/role catalog OIDs and becomes `ready`. `begin_job` changes an idle `ready` or `retained` lease to `in_use`. Only its registered supervisor may finish that job. Success returns to `ready`; failure returns to `retained`. An automatic successful run then releases the lease. Explicit retain keeps the resource unavailable until its owner releases it.

Release requires the exact lease ID, generation and canonical worktree, no managed jobs, and a ready/retained state. It records `cleaning` before resource operations. Confirmed cleanup changes the slot to `free`; uncertainty changes it to `quarantined`. A duplicate release is harmless until reuse. Once a new generation owns the slot, every old command is stale and cannot touch it.

Linux must provide `pidfd_open` and `pidfd_send_signal`, and Python must expose both APIs. Startup probes the actual syscalls before launching a child; unsupported kernels fail closed. The supervisor requires child-subreaper support, registers the child before permitting execution, and waits through orphaned descendants, including children starting a new session. SIGHUP detaches without stopping managed children. SIGINT and SIGTERM signal only verified live descendants through Linux pidfds, including orphans after the original launcher exits. Each signal handles a verified descendant snapshot. Children can ignore a signal or fork afterward; repeated signals rescan. There is no automatic forced escalation or bounded termination promise. The supervisor keeps the lease until every descendant exits; it never signals a recycled PID or an unknown process. The tool reads process IDs, parent/session IDs, boot ID, start times and socket ownership. It never reads full process arguments or environments. It never signals an unknown listener or database session.

A free port alone never establishes database ownership. Acquisition skips occupied ports. Before launch, the supervisor binds the port again. TEST commands retain that reservation for their complete lifetime. DEV commands hand the socket to the server by closing the reservation immediately before execution, then inspect listening socket ownership immediately and at most four times per second during supervision. A foreign listener during that handoff quarantines the lease; it is never killed. Temporary helper servers may still use port 0.

A bind conflict before any managed child starts is a known preparation failure. It retains the idle database with a static diagnosis, so its exact owner can retry or release it through the ordinary catalog/client cleanup guards. The listener is untouched. This differs from a foreign listener after launch, when process/resource ownership is uncertain and quarantine remains necessary.

Listener ownership inspection checks the port and process, not the local bind address. The supported NewYou configuration currently binds `127.0.0.1`; preserving and proving loopback binding is a mandatory WELL-147 consumer acceptance check before integration/activation. DevCore does not turn an arbitrary wildcard-binding command into a loopback-only server. Do not claim that its ownership check enforces network locality.

Process identity combines PID, Linux boot ID and start time. Registry changes use fsync and atomic rename under flock. Recovery never trusts an elapsed heartbeat. `slots recover` quarantines interrupted preparation, cleanup or dead supervisors. A killed supervisor can leave live descendants, so recovery does not reclaim that allocation even when its original PID or HTTP listener is gone. This conservative quarantine also covers machine restart. No automatic repair deletes uncertain resources.

Read-only status and unchanged exhaustion/wait passes hold the same lock but do not rewrite or fsync unchanged registry contents.

If cleanup failed before removing either recorded identity, with no jobs, its exact owner may retry after the problem resolves:

```sh
devcore-project slots recover --lease LEASE --generation GENERATION
```

The retry repeats every endpoint, OID, ownership and client guard. It cannot recover interrupted preparation, supervisor loss or partial cleanup where the database was removed but role deletion failed. A missing catalog identity remains quarantined; the tool never adopts or deletes a residual role from its name alone. Those cases require a separately reviewed exact-target reconciliation procedure; editing the registry to force availability is unsupported.

## Disposable database boundary

Provisioning uses the existing DevCore administrative role inside the inspected TEST container. Every SQL operation addresses that immutable container ID, not a mutable name. The adapter requires its running loopback mapping to match `127.0.0.1:55433`. It creates identities only when both database and role are absent. A creation race fails closed rather than adopting the winner.

The runtime role has `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`, no role memberships and no database ownership. The database owner is the existing `devcore_admin`, which runtime credentials cannot assume. The database starts with connections disabled, loses all PUBLIC database privileges, receives only runtime CONNECT and TEMPORARY without grant options, then enables connections. The administrator grants runtime USAGE and CREATE on its public schema for migration objects. Runtime credentials receive no database CREATE permission and cannot reopen CONNECT for PUBLIC or another slot role. Current NewYou migrations create application objects and Ash functions in public; actual branch migration proof remains WELL-147. Provisioning does not grant privileges on legacy or unrelated allocations. See PostgreSQL's [GRANT semantics](https://www.postgresql.org/docs/18/sql-grant.html).

Before cleanup the tool verifies the approved project/TEST endpoint, registered names, generation, stored container ID, database OID, role OID, recorded administrator owner OID, exact ownership comments, administrator database ownership, least-privilege flags, absence of memberships or any runtime-owned databases, no managed jobs and zero database clients. It disables new logins/connections for that exact generation and repeats the catalog/client checks. It uses plain `DROP DATABASE` and `DROP ROLE`, never FORCE or session termination. A connection race or remaining client fails cleanup and quarantines the slot. Partial cleanup also quarantines it. A prefix, port or comment alone grants no cleanup authority.

`new_you_dev`, `new_you_test`, `postgres`, template databases, production targets, unregistered databases and unrelated projects are outside the accepted identities. Fresh generation names fence stale processes from a later lease. NewYou, not DevCore, applies the current branch's migrations and owning business interfaces for fixtures. DevCore never clones an existing database or seeds participant records.

## Secrets and evidence

Generation passwords are random and appended under DevCore's existing canonical state lock to `~/.config/dev-core/project-db.env`. Existing secrets are preserved. Runtime passwords and SQL travel through standard input or environment injection, never command arguments. No runtime role gains CREATEDB. `slots status` contains only non-secret identities, states, endpoints and operational diagnoses.

Managed rendering uses private immutable snapshots and the existing DevCore renderer. The snapshots replace only the TEST binding in a private project declaration, never the tracked declaration or worktree `.env` files. They are removed after loading, including failed rendering. TEST jobs exclude DEV database credentials. Inherited generic PostgreSQL variables are removed. After merging, `PG*`, names containing `DATABASE_URL`, `DB_URL`, names ending in `_DB_URL`, and unknown `DEV_DATABASE_*`/`TEST_DATABASE_*` keys fail closed. Only HOST, PORT, NAME, USERNAME and PASSWORD are supported under those two prefixes. DEV jobs import only TEST database keys from the TEST template for child probes. Supplemental secrets are applied directly from the canonical store for the active profile plus `all`, even without template tokens; every declared variable is cleared before active bindings are applied. Inactive-profile values are never imported from TEST templates or inherited environments. Build/dependency overrides resolving outside the worktree fail closed. Nonempty `MIX_TEST_PARTITION` fails closed before rendering and after all template and supplemental bindings are merged. Final DEV-profile bindings must also match the fixed shared DEV endpoint, project role/database and canonical DEV secret. TEST jobs exclude those DEV bindings.

Each managed job retains a private output log and structured result under the registry's `runs/JOB` directory before cleanup. Known project and generation secrets are redacted across output chunk boundaries. Treat application output as potentially sensitive. Do not routinely publish logs or participant data. The tool preserves diagnostic records and generated secret entries; it does not implement their automatic retention purge. A failed run keeps its database unavailable until explicit release.

Managed snapshot rendering waits up to 30 seconds only when the existing renderer
returns the exact pre-mutation state-lock contention diagnosis with no stdout.
Every attempt still acquires the canonical locks. Other failures stop immediately;
timeout or cancellation removes the private snapshot and preserves the allocation.
The lock is held only for rendering. It does not serialize managed child jobs or
database suites. Direct legacy mutation commands retain nonblocking admission.

## Capacity and remaining proof

On 2026-11-17, the workstation reported 24 logical CPUs and 33,562,959,872 bytes of RAM. The provisional heavy cap is `max(1, min(2, cpus / 4, total_memory / 8 GiB))`, rounded down. This gives two heavy jobs on that host. Capacity permits persist with lease/generation identity; supervisor loss cannot silently release them to a new heavy job. A provably pre-launch failure returns its heavy permit; a failed launch is retained without an active job. Once launch ownership is uncertain, the permit is quarantined and needs reviewed reconciliation. Waiting for heavy capacity is bounded to 3600 seconds and can be interrupted. It is a conservative configuration bound, not a measured guarantee for two full NewYou suites. WELL-147 must measure peak memory and actual suite/build behavior before activation, accounting for other active work. Database slots do not globally serialize focused tests, and the heavy gate is not a PLT lock.

Local metadata/adaptor tests cover 20 separate claiming processes, exhaustion, ownership, retained failures, quarantine, orphan descendants, killed supervisors, port conflicts, approval identity and environment handling. DevCore's CI-owned PostgreSQL integration additionally tests committed synthetic row isolation, denied cross-slot connections, NOCREATEDB and fresh reuse. This does not prove NewYou migrations, business fixtures, all child paths or PLT concurrency. Those remain explicit WELL-147 obligations.
