# DevCore managed slots implementation plan

Owner brief and WELL-145 authorize DevCore first. NewYou runtime changes and live activation are separate deliverables. No existing database or agent may be changed.

The executable remains one installable Bash file. A marked embedded Python module owns slot lifecycle logic and can be loaded by the unit tests without invoking the CLI. It uses Linux flock, atomic fsync/rename registry updates, boot ID and process start times. Registry ownership alone never authorizes database adoption.

- [x] Add failing adapter-based tests for 20 atomic claims, exhaustion, stale generation, cross-worktree ownership, release, retained failure, quarantine, interrupted provisioning, occupied ports and recovery.
- [x] Implement the private registry, explicit transition guards and exact opt-in manifest. Require a matching local authorization receipt before provisioning or cleanup. A generation gets a unique database and runtime role. Never adopt a pre-existing identity.
- [x] Add failing PostgreSQL adapter tests. Implement stdin-only administrative SQL, endpoint binding, catalog OID/comment ownership checks, least-privilege role creation, PUBLIC connection revocation and zero-client cleanup without FORCE or session termination.
- [x] Add failing command/environment tests. Implement command-specific render snapshots using the existing renderer and canonical secret store, supervised children, automatic opt-in run acquisition and retention on failure. Preserve ordinary v1 projects and the single-file installer.
- [x] Document the NewYou consumer contract, lifecycle, bounded cleanup manifest, staged activation and rollback. Record subprocess and PLT proof required in the separate NewYou PR. Do not remove legacy booking instructions or claim application isolation is proven.
- [ ] Run all DevCore unit, syntax, ShellCheck and provenance checks. Inspect the complete diff, commit source, run OCR and request independent review against exact base/head. Open a focused PR as JC-Agents. No live installation, activation, release publication or merge.

Use focused red/green commands while iterating, then `python3 -m unittest discover -s tests -v`, `bash -n bin/devcore-project install/install.sh install/rollback.sh`, `shellcheck bin/devcore-project install/install.sh install/rollback.sh`, and the provenance checks in CI. Tests use temporary metadata and injected adapters, never workstation databases. Integration uses existing CI-owned disposable PostgreSQL only when explicitly selected by its opt-in environment.
