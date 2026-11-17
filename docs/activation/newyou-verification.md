# DevCore slot verification record

This record describes the DevCore source prerequisite, not live activation or completed NewYou integration. WELL-145 is the source issue; WELL-147 is the separate NewYou integration/proof dependency. Plane and the exact PR retain current execution/CI/review state.

Source base is `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`. Implementation checkpoint is `1e10975b518a1301a70839517e7938188f7acc7b`. Its executable SHA-256 is `383370ed4b25e20af8dbb4c347783c0310380c924a8772bfa49b7ff4a1813831`. Documentation-only commits may follow without changing that executable. The canonical source is `Carpe-Diem-Media/devcore-project`; the historical personal URL redirects there. This branch uses source version 1.2.0 and has no release tag.

The installed executable was inspected, not patched. It reports 1.1.0 with SHA-256 `df7dd3263197d33416b99699b5f09ee2b37bb4a45f55cc2a7bb4164dbbff9568`. No installation, live activation, database provisioning/drop, service change or agent migration occurred. Port 4237 remained occupied during read-only inspection. The initial legacy TEST/PLT holder PID 4026121 later released its lock without intervention by this work.

## Observed local checks

Commands ran from the isolated DevCore worktree rooted at `.worktrees/newyou-slots` unless a different directory is stated. Tool versions were Python 3.15.2, ShellCheck 0.11.0 and OCR 1.13.11. Linux headers confirm `PR_SET_CHILD_SUBREAPER` is 36; runtime tests exercise it.

- Baseline `python3 -m unittest discover -s tests -q` at source base ran 77 tests successfully, with two opt-in PostgreSQL integration skips.
- Focused red/green commands used `python3 -m unittest tests.test_slots -q` and individual named cases. They first failed for the missing allocator, administrative adapter and supervisor. Later regression cases failed for stdin loss, container-name SQL targeting, self-issued activation references, retained secret snapshots, discarded build overrides and missing heavy-capacity fencing/classification, then passed after their corresponding fixes.
- An early full working-candidate gate failed only `DevCoreBaselineTests.test_repository_owned_version_is_reported`, which still expected 1.1.0 after the intentional source version bump. The assertion was updated to the reviewed 1.2.0 source version. This was a changed-input correction, not an unchanged retry.
- Final `python3 -m unittest discover -s tests -v` ran 126 tests in 46.979 seconds and returned `OK (skipped=3)`. The three skips are the explicitly opt-in PostgreSQL integration tests. This means 123 executed tests passed locally, not that live SQL isolation was proved locally. The new slot module has 48 focused tests.
- `bash -n bin/devcore-project install/install.sh install/rollback.sh` passed.
- `shellcheck bin/devcore-project install/install.sh install/rollback.sh` passed.
- `git diff --check` and the staged equivalent passed. The complete staged implementation diff was inspected for scope, credentials, generated env files and destructive targets. All test credentials are synthetic.
- From `provenance/legacy-v1.0.0`, `sha256sum --check SHA256SUMS` passed. In a temporary archive extraction, `sha256sum --check SHA256SUMS.txt` passed, and the bundled executable matched `d30a90ba12c5394ec573ced1cdf80362c428280f7231c186ef7d05aa489adfd5`.
- An early syntax/lint batch was mistakenly invoked from the provenance directory and failed to find the relative source paths. Both checks were then rerun from the repository root and passed as recorded above.

The standard local command skips Docker integration. The existing hosted `postgres-integration` job runs `DEVCORE_RUN_POSTGRES_INTEGRATION=1 python3 -m unittest tests.test_postgres_integration -v` against only its own labelled disposable containers. The new scenario provisions two fresh generations concurrently, commits distinct synthetic markers, denies cross-slot connections and CREATEDB, releases one generation without changing the other, and proves a fresh reacquisition has no old table. Its hosted result must be checked against the exact final PR head. No local workstation database substitutes for this proof.

OCR was invoked as `ocr review --from origin/main --to HEAD` on implementation checkpoint `1e10975b518a1301a70839517e7938188f7acc7b` with comparison base `6446dc428ae3ef2edb8d11b9f94aea0128854d1d`, after local gates passed. The exact outcome, coverage, exclusions and any quota error belong in the PR's OCR Review Findings and Plane record. No OCR result is asserted here before it is observed. Native independent review must also inspect the exact final diff, head, authority and CI. Neither review authorizes merge or activation by itself.

## Reviewable installation and rollback commands

These commands are a proposed installation procedure for this exact source artifact. They have not run against the live workstation. Execute them only after independent source review and explicit owner installation authorization. If the reviewed source changes, recompute its checksum and use the newly approved artifact. Do not silently install a moving branch.

From the exact reviewed DevCore checkout:

```sh
git rev-parse HEAD
sha256sum bin/devcore-project
bash install/install.sh --source bin/devcore-project --version 1.2.0 --sha256 383370ed4b25e20af8dbb4c347783c0310380c924a8772bfa49b7ff4a1813831
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
