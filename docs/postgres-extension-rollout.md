# PostgreSQL 18.7 and pgvector rollout

The candidate image builds pgvector 0.8.7 against the pinned PostgreSQL
18.7 Alpine 3.24 base. Build and test it on disposable containers first.

```sh
docker build -t devcore-postgres:18.7-vector0.8.7 postgres
docker image inspect devcore-postgres:18.7-vector0.8.7 --format '{{.Id}} {{.Os}}/{{.Architecture}}'
docker run --rm --entrypoint sh devcore-postgres:18.7-vector0.8.7 -ec 'postgres --version; test -f "$(pg_config --pkglibdir)/vector.so"; ! command -v gcc'
DEVCORE_RUN_POSTGRES_INTEGRATION=1 DEVCORE_POSTGRES_TEST_IMAGE=devcore-postgres:18.7-vector0.8.7 python3 -m unittest discover -s tests -p test_postgres_integration.py
```

## Before cutover

Inventory every database, including templates and databases that reject
connections, and record owners, database ACLs and settings, roles,
memberships, database sizes, and tablespaces. Capture Compose and
PostgreSQL configuration, authentication files, and the original image ID.
Keep credentials and backup files in a restricted directory. Check free
space for the logical dumps, physical recovery point, and isolated restore
volumes. Measure each operation and record the application write outage.

Review the [PostgreSQL 18.7 release notes](https://www.postgresql.org/docs/18/release-18-7.html).
Inventory GiST indexes using `gist_trgm_ops` and B-tree indexes on
`bpchar` columns in each connectable database. Plan targeted reindexing
for those indexes. Review other release-note reindex cases against
observed symptoms or affected workloads. Review PostgreSQL, collation and
tablespace configuration before scheduling the change. Use a new full
backup as the starting point for any incremental backups after updating.

## Backup and isolated recovery

1. Quiesce application writers and provisioning. Use PostgreSQL 18.7
   client binaries for `pg_dumpall --globals-only` and per-database
   `pg_dump --format=custom --create`. Use an explicit inventory and
   account for any database that cannot be dumped. Capture configuration
   files independently. Record successful exit status, archive sizes and
   checksums. Globals may contain password verifiers.
2. Take a supported full physical backup with `pg_basebackup` and WAL,
   or stop PostgreSQL cleanly and snapshot all data and tablespace
   mounts together. A running Docker volume file copy is unsafe.
   Check tablespace paths and save any required mapping for restore.
3. Restore logical globals and databases into a fresh isolated cluster
   with matching locale and tablespaces. Use the source bootstrap
   administrator when restoring globals with explicit membership grantors. Inspect the dump and omit the single
   duplicate bootstrap CREATE ROLE statement while retaining its ALTER
   ROLE attributes and grants. Use
   `psql -X -v ON_ERROR_STOP=1` and `pg_restore --exit-on-error --create`.
   Handle restore of the bootstrap database and reviewed tablespace
   mappings explicitly. Check inventory, ownership, ACLs, memberships,
   role login and representative queries. Restore the physical backup
   separately and verify recovery and the same invariants.
4. Rehearse replacing only the PostgreSQL container with the candidate
   on a copy of the restored volume. Run doctor and application
   migrations on disposable projects, and verify vector operations as
   a non-superuser. Rehearse recovery with the original image and
   pre-change recovery point while writes remain quiesced.

## Approval and rollback

Shared rollout requires explicit authorization and independent review of
the exact candidate, rehearsal evidence and CI. Two Compose image
references are the proposed workstation change. Roll out TEST first
and validate it before seeking approval for DEV. Preserve both existing
volumes and the pre-change recovery point.

Before vector-dependent writes, rollback uses the original image and
verified pre-change data state. Validate authentication, database
inventory and application queries before resuming writes. After
vector-dependent writes, use a vector-capable recovery image to preserve
the new data. Recovery to the pre-change snapshot would lose later
writes and requires a separate decision.

## Local rehearsal evidence

- The Linux amd64 candidate built locally as image index
  `sha256:c41ec08b3d88535cf84e705cced68f199f40410c60218be157f3435a1544a929`.
  The runtime reports PostgreSQL 18.7. PostgreSQL successfully loads the
  pgvector 0.8.7 library and executes its cosine-distance operator.
  Publish and record the final registry digest before any rollout.
- Run the synthetic backup, isolated restore, image replacement and
  rollback with `bash tests/rehearse_postgres_recovery.sh`. The run
  produced a 902-byte globals dump, a 1,482-byte custom database dump
  and a 49,407,488-byte cold archive. The cold capture, replacement and
  rollback sequence took 6 seconds. The full rehearsal took 9 seconds.
  These timings include disposable setup. Measure the actual write
  outage separately on a representative restore.
- A read-only scan inspected 12 connectable DEV databases and 1,668
  connectable TEST databases. No `gist_trgm_ops` or `bpchar` B-tree
  indexes matched. One non-connectable template per cluster was
  excluded. Both clusters had only the default tablespaces,
  `wal_level=replica`, WAL summaries disabled and data checksums enabled.
  The C-function inventory found only bundled PostgreSQL libraries,
  including the installed `btree_gist`, `citext`, `pgcrypto`, and
  `plpgsql` modules. The derivative rebuilds pgvector against 18.7.
  Refresh this inventory and review any other release-note conditions
  immediately before authorizing maintenance.
- The sum of database sizes was about 122 MB for DEV and 26.1 GB for
  TEST. The rehearsal host had 15.1 GB free under the temp directory
  and 242 GB on the Docker data filesystem. Size a protected backup
  destination separately before a representative restore. Allow room
  for WAL, retained source data, dumps, and recovery copies. Synthetic
  backup sizes do not establish capacity or downtime for the shared fleet.

To run the optional application compatibility fixture, set
`DEVCORE_ASH_FIXTURE_PROJECT` to a VGAS checkout with its locked TEST
dependencies compiled and run the integration suite with VGAS's pinned
Erlang and Elixir on PATH. The fixture starts only its own Repo against
the disposable TEST allocation via `devcore-project run test`.
It generates AshPostgres migrations into a temporary directory, applies
them as the project owner, uses the Ash AI manual vectorization action
with a deterministic embedding model, and verifies ranked retrieval
through Postgrex and the AshPostgres cosine-distance function. The full
VGAS F01 retrieval workflow still needs its own application verification.
