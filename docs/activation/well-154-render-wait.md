# WELL-154 private-environment contention correction

This is a source correction for the separate WELL-147 NewYou pilot. Its base is
`1a46dcc54d3ac37fa554955e20c45555c0e08f5b`. Code checkpoint
`3cf7634331593caf548880dc66f99cdbfe6a2d00` reports version 1.2.1 and executable
SHA-256 `2ed9f8bba9abd3775b578bf159bb1c01787dac33cbbc668d71849752171916b7`.
It is not installed, released or approved for merge by this document.

## Defect and correction

The installed 1.2.0 NewYou two-worktree pilot failed one environment preparation
with the generic managed-render error while its sibling progressed. That attempt
did not retain the renderer's captured stderr, so its exact underlying failure
cannot be reconstructed from that message alone. Independent temporary-state
reproduction confirmed a concrete concurrency defect: the renderer rejects a busy
canonical state lock immediately, and managed preparation did not wait.

The same reproduction found that failure cleanup closed the directory descriptor
twice. The second close masked the known busy result with an EBADF traceback.
The outer finally now owns that descriptor. The managed snapshot caller retries
only exit 1 with empty stdout and the exact static busy diagnosis. A monotonic
30-second deadline includes renderer execution and retry delays. Timeout and
cancellation remove the private snapshot; unrelated or partial-output failures
stop without retry. No lock validation, secret authority, database privilege,
cleanup guard or manifest field changes.

## Observed source proof

Local Python is 3.15.2. All tests use temporary metadata and synthetic credentials.
No test uses a workstation database.

- `python3 -m unittest tests.test_slots -q`: baseline 73 passed in 18.108 seconds.
- The held-lock environment test failed before correction. The exact busy-result
  test failed because of the traceback. Timeout/parallel tests also failed before
  the final matcher and descriptor correction; those failures remain recorded.
- `python3 -m unittest tests.test_slots.EnvironmentTests -q`: 24 passed in 15.531
  seconds, including actual temporary lock contention, distinct parallel snapshots,
  timeout, cancellation, unknown failure, redaction and snapshot removal.
- `python3 -m unittest discover -s tests -q`: final version 1.2.1 source ran 158
  tests in 57.242 seconds, with 155 executed passes and three opt-in SQL skips.
- `bash -n bin/devcore-project install/install.sh install/rollback.sh`,
  `shellcheck bin/devcore-project install/install.sh install/rollback.sh` and
  `git diff --check` passed.

Hosted PostgreSQL integration, exact-head CI, bounded OCR and independent final
review remain separate required evidence. Neither unchanged-input retries nor
the temporary binding tests establish completed workstation isolation.

## Workstation boundary and next activation

Installed 1.2.0 remains the previously authorized artifact, with checksum
`e76cb9206d6e00226ab9549bfa2a342c4da867f2a7d21956240035b1bf65d93a` and its installer
backup preserved. The authenticated owner manifest comment 6952421506 was accepted
and the unchanged contract was enabled for the bounded NewYou pilot. New
acquisitions were subsequently disabled after the failed diagnostic pilot.

Two pilot generations are quarantined after supervisor loss. Their databases,
private logs, secret entries and registry records remain preserved. This patch
does not reconcile or delete them and does not loosen the existing conservative
recovery contract. Any reconciliation must follow an independently reviewed
procedure for those exact targets. Existing DEV, shared TEST and other agents
remain outside this patch.

After source integration and resulting-main verification, installation requires
separate authorization for the exact 1.2.1 source and checksum above. The earlier
1.2.0 installation approval does not cover it. The cleanup manifest digest remains
`3fb71d0ed24dfc4ab8ef75226916da624f5ca4a18343695a154733eb2a93e556`; its bounded
approval does not authorize deleting unknown resources or changing existing ACLs.
Recheck the installed artifact and manifest before re-enabling acquisitions, then
complete WELL-147's live application isolation/reuse, heavy-capacity and final
repository gates. No existing worktree switches automatically.
