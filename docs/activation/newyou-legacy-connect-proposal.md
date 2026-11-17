# Proposed legacy TEST connection boundary

Status is `NOT_AUTHORIZED` and `NOT_EXECUTED`. This proposal is separate from the registered-generation cleanup manifest. WELL-145 currently prohibits changes to existing allocation privileges. Read-only workstation checks confirmed the boundary described below; no privilege change was performed.

PostgreSQL grants CONNECT to PUBLIC by default. Revoking privileges only on a newly created slot database denies cross-slot connections, but does not stop its LOGIN role from connecting to a legacy database that permits PUBLIC. A per-role REVOKE cannot override PUBLIC. These are connection permissions; this finding does not establish access to legacy application tables. See the official [privilege documentation](https://www.postgresql.org/docs/current/ddl-priv.html).

The source now refuses to provision managed roles unless a read-only ACL query proves that `new_you_test` does not permit PUBLIC CONNECT. With an unchanged default legacy ACL, the feature remains unavailable. No slot acquisition falls back to shared TEST.

## Exact proposed scope

- Project is NewYou, environment TEST, endpoint `127.0.0.1:55433`, container `dev-core-postgres-test-1`, administrative role `devcore_admin`.
- The sole existing database target is `new_you_test`, owned by runtime role `new_you_test`.
- Read-only preflight on 2026-11-17 observed database OID `4687800`, owner CONNECT true, PUBLIC CONNECT true, owner NOCREATEDB/NOSUPERUSER, zero role memberships and no connected roles at that instant. The private receipt records the inspected immutable container ID and ACL. Recheck all identities before an approved operation; an old OID is not permanent authority. `mise exec -- devcore-project doctor` passed DEV and TEST endpoint/authentication checks before this metadata query.
- The proposed mutation is exactly `REVOKE CONNECT ON DATABASE new_you_test FROM PUBLIC;`.
- Preserve every row, database, role, password, explicit role grant and all other privileges. Do not change DEV, HBA, services, existing client sessions, other databases or runtime privilege flags.
- Before mutation, bind the immutable container ID and exact database OID/owner to a private non-secret receipt. Confirm the expected owner remains NOCREATEDB, has no unexpected memberships and retains CONNECT. Inspect only this target's connection-role identities and ACL, without query text or environment values. Identify any legitimate non-owner role that currently depends on PUBLIC. Its explicit grant would require a separately reviewed addition to this scope.

## Procedure requiring approval

1. Obtain an owner-approved scope change for this exact target and operation. Use a separate reviewed DevCore change or exact operational procedure; this document is not an executable migration or authorization.
2. Recheck repository/Plane authority, current endpoint/container identity and target OID/owner. Capture the original ACL and explicit CONNECT grants locally. Coordinate any affected consenting legacy user. If an unidentified role depends on PUBLIC, stop before mutation.
3. Within a transaction, assert the recorded OID/owner, verify expected ACL and owner CONNECT, perform only the stated REVOKE and recheck owner CONNECT. Roll back on uncertainty. The owner role's privileges and explicit grants remain available; existing connections are not terminated.
4. Verify authenticated legacy-owner reconnection through DevCore and managed-role denial against legacy TEST. Use no fixture writes to the retained database. Record exact commands and non-secret outcomes. Run the normal legacy compatibility gates only after existing lock ownership permits them.
5. If the original ACL allowed PUBLIC CONNECT, the proposed inverse is exactly `GRANT CONNECT ON DATABASE new_you_test TO PUBLIC;`, only for the same recorded OID/owner. Rollback would reopen the boundary. It requires separate owner authorization and must wait until all managed roles have been released or otherwise fenced under their approved cleanup contract. Never reopen access while live managed identities depend on that boundary.

The CI isolation scenario creates its own disposable legacy analogue. It proves default PUBLIC blocks managed provisioning before credentials/roles exist, then simulates the approved REVOKE only inside that CI-owned container. It checks that owner CONNECT survives and a managed role cannot connect to the analogue. This is not authority or evidence for changing the workstation allocation.
