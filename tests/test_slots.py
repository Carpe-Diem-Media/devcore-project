"""Slot tests use temporary metadata and adapters, never workstation databases."""
import concurrent.futures
import copy
import json
import os
import socket
import subprocess
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "devcore-project"
BEGIN = "# DEVCORE_SLOTS_PYTHON_BEGIN\n"
END = "# DEVCORE_SLOTS_PYTHON_END"


def module():
    source = TOOL.read_text()
    if BEGIN not in source:
        return None
    result = types.ModuleType("devcore_slots")
    before, embedded = source.split(BEGIN, 1)
    aligned = "\n" * (before.count("\n") + 1) + embedded.split(END, 1)[0]
    exec(compile(aligned, str(TOOL), "exec"), result.__dict__)
    return result


def approve_for_test(digest, reference):
    return {"author": "JCSchoeman96", "synthetic": True}


class Resources:
    def __init__(self):
        self.created = {}
        self.dropped = []
        self.fail_create = False
        self.fail_clean = False
        self.clients = set()

    def prepare(self, lease):
        if self.fail_create:
            raise RuntimeError("injected preparation failure")
        self.created[lease["database"]] = lease["generation"]
        return {"database_oid": 1000 + lease["slot"], "role_oid": 2000 + lease["slot"]}

    def cleanup(self, lease):
        if self.fail_clean or lease["database"] in self.clients:
            raise RuntimeError("clients remain or cleanup failed")
        assert self.created[lease["database"]] == lease["generation"]
        self.dropped.append(lease["database"])
        del self.created[lease["database"]]


class SlotTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertIsNotNone(self.m, "managed slot allocator is missing")
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-slots-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.resources = Resources()
        self.contract = self.m.newyou_contract()
        self.pool = self.m.Pool(self.root / "pool", self.contract, self.resources,
                                port_available=lambda port: True, approval_check=approve_for_test)
        self.pool.enable(self.pool.manifest_digest(), "synthetic-owner-authorization")
        self.worktree = str(self.root)

    def claim(self):
        return self.pool.acquire(self.worktree)

    def release(self, lease):
        return self.pool.release(lease["lease_id"], lease["generation"], self.worktree)

    def test_twenty_concurrent_claims_and_exhaustion(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            leases = list(executor.map(lambda _: self.claim(), range(20)))
        self.assertEqual({x["slot"] for x in leases}, set(range(1, 21)))
        for key in ("lease_id", "generation", "port", "database", "role"):
            self.assertEqual(len({x[key] for x in leases}), 20, key)
        self.assertEqual({x["port"] for x in leases}, set(range(4221, 4241)))
        with self.assertRaisesRegex(self.m.SlotError, "exhausted"):
            self.claim()

    def test_release_and_reuse_have_fresh_database_generation(self):
        old = self.claim()
        self.release(old)
        new = self.claim()
        self.assertEqual(old["slot"], new["slot"])
        self.assertNotEqual(old["generation"], new["generation"])
        self.assertNotEqual(old["database"], new["database"])
        with self.assertRaisesRegex(self.m.SlotError, "stale"):
            self.release(old)
        self.assertEqual(self.pool.status()[0]["lease_id"], new["lease_id"])

    def test_status_and_exhausted_wait_do_not_rewrite_unchanged_registry(self):
        from unittest.mock import patch
        for _ in range(20):
            self.claim()
        with patch.object(self.m, "atomic_json", wraps=self.m.atomic_json) as write:
            self.pool.status()
            with self.assertRaisesRegex(self.m.SlotError, "exhausted"):
                self.pool.acquire(self.worktree, wait=0.12)
        write.assert_not_called()

    def test_wrong_worktree_or_generation_cannot_release(self):
        lease = self.claim()
        for generation, worktree in (("bad", self.worktree), (lease["generation"], "/tmp")):
            with self.assertRaises(self.m.SlotError):
                self.pool.release(lease["lease_id"], generation, worktree)
        self.assertEqual(self.resources.dropped, [])

    def test_duplicate_release_is_idempotent_until_slot_reused(self):
        lease = self.claim()
        self.release(lease)
        self.release(lease)
        self.assertEqual(self.resources.dropped, [lease["database"]])

    def test_port_conflict_skips_without_signalling(self):
        self.pool.port_available = lambda port: port != 4221
        self.assertEqual(self.claim()["slot"], 2)

    def test_cleanup_failure_quarantines(self):
        lease = self.claim()
        self.resources.fail_clean = True
        with self.assertRaisesRegex(self.m.SlotError, "quarantined"):
            self.release(lease)
        self.assertEqual(self.pool.status()[0]["state"], "quarantined")

    def test_connection_boundary_failure_keeps_empty_slot_reusable_with_nonsecret_diagnosis(self):
        from unittest.mock import patch
        self.assertTrue(hasattr(self.m, "ConnectionBoundaryError"))
        with patch.object(self.resources, "prepare", side_effect=self.m.ConnectionBoundaryError("synthetic_secret")):
            for _ in range(21):
                with self.assertRaisesRegex(self.m.SlotError, "legacy TEST PUBLIC CONNECT") as error:
                    self.claim()
        row = self.pool.status()[0]
        self.assertEqual(len(self.pool.status()), 1)
        self.assertEqual(row["state"], "free")
        self.assertIn("legacy TEST PUBLIC CONNECT", row["diagnosis"])
        self.assertNotIn("synthetic_secret", str(error.exception) + json.dumps(row))
        self.assertEqual(self.claim()["slot"], 1)
        self.assertEqual(self.claim()["slot"], 2)

    def test_remaining_clients_prevent_reuse(self):
        lease = self.claim()
        self.resources.clients.add(lease["database"])
        with self.assertRaises(self.m.SlotError):
            self.release(lease)
        self.assertEqual(self.resources.dropped, [])

    def test_preparation_failure_is_quarantined_never_adopted(self):
        self.resources.fail_create = True
        with self.assertRaises(self.m.SlotError):
            self.claim()
        self.assertEqual(self.pool.status()[0]["state"], "quarantined")
        self.assertEqual(self.resources.dropped, [])

    def test_retention_and_explicit_release(self):
        lease = self.claim()
        self.pool.retain(lease["lease_id"], lease["generation"], self.worktree)
        self.assertEqual(self.pool.status()[0]["state"], "retained")
        self.assertEqual(self.claim()["slot"], 2)
        self.release(lease)

    def test_live_job_blocks_release_and_recovery(self):
        lease = self.claim()
        job = self.pool.begin_job(lease["lease_id"], lease["generation"], self.worktree)
        with self.assertRaisesRegex(self.m.SlotError, "managed job"):
            self.release(lease)
        self.pool.recover()
        self.assertEqual(self.pool.status()[0]["state"], "in_use")
        self.pool.end_job(lease["lease_id"], lease["generation"], self.worktree, job, 0)
        self.release(lease)

    def test_dead_supervisor_quarantines_never_reclaims(self):
        lease = self.claim()
        self.pool.begin_job(lease["lease_id"], lease["generation"], self.worktree)
        self.pool.process_alive = lambda identity: False
        self.pool.recover()
        self.assertEqual(self.pool.status()[0]["state"], "quarantined")
        with self.assertRaises(self.m.SlotError):
            self.release(lease)
        self.assertEqual(self.resources.dropped, [])

    def test_failed_job_is_retained(self):
        lease = self.claim()
        job = self.pool.begin_job(lease["lease_id"], lease["generation"], self.worktree)
        self.pool.end_job(lease["lease_id"], lease["generation"], self.worktree, job, 1)
        row = self.pool.status()[0]
        self.assertEqual(row["state"], "retained")
        self.assertEqual(row["last_exit"], 1)

    def test_manifest_authorization_is_required_and_bound(self):
        pool = self.m.Pool(self.root / "disabled", self.contract, self.resources)
        with self.assertRaisesRegex(self.m.SlotError, "authorization"):
            pool.acquire(self.worktree)
        with self.assertRaises(self.m.SlotError):
            pool.enable("wrong", "not-an-approval")
        altered = copy.deepcopy(self.contract)
        altered["test_port"] = 55432
        with self.assertRaises(self.m.SlotError):
            self.m.Pool(self.root / "invalid", altered, self.resources)

    def test_protected_or_tampered_target_refuses_cleanup(self):
        lease = self.claim()
        with self.pool.registry() as state:
            state["slots"]["1"]["database"] = "new_you_test"
        with self.assertRaises(self.m.SlotError):
            self.release(lease)
        self.assertEqual(self.resources.dropped, [])

    def test_private_metadata_and_symlink_rejection(self):
        lease = self.claim()
        self.assertEqual(self.pool.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.pool.root / "registry.json").stat().st_mode & 0o777, 0o600)
        link = self.root / "link"
        link.symlink_to(self.pool.root)
        with self.assertRaises(self.m.SlotError):
            self.m.Pool(link, self.contract, self.resources)
        self.release(lease)

    def test_wait_is_bounded_and_cancelled_without_shared_fallback(self):
        for _ in range(20):
            self.claim()
        with self.assertRaisesRegex(self.m.SlotError, "exhausted"):
            self.pool.acquire(self.worktree, wait=0.01)
        with self.assertRaisesRegex(self.m.SlotError, "cancelled"):
            self.pool.acquire(self.worktree, wait=1, cancelled=lambda: True)

    def test_retry_cleanup_after_clients_leave_keeps_same_exact_target(self):
        lease = self.claim()
        self.resources.fail_clean = True
        with self.assertRaises(self.m.SlotError):
            self.release(lease)
        self.resources.fail_clean = False
        self.pool.release(lease["lease_id"], lease["generation"], self.worktree, retry=True)
        self.assertEqual(self.pool.status()[0]["state"], "free")

    def test_disabling_acquisition_preserves_existing_leases_and_cleanup(self):
        lease = self.claim()
        self.pool.disable()
        with self.assertRaisesRegex(self.m.SlotError, "disabled"):
            self.claim()
        self.assertEqual(self.pool.status()[0]["state"], "ready")
        self.release(lease)

    def test_real_socket_bind_conflict(self):
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            self.assertFalse(self.m.port_available(held.getsockname()[1]))

    def test_interrupted_preparation_and_cleanup_are_quarantined_without_deletion(self):
        for state_name, owner_key in (("preparing", "preparer"), ("cleaning", "cleaner")):
            lease = self.claim()
            with self.pool.registry() as state:
                row = state["slots"][str(lease["slot"])]
                row["state"] = state_name
                row[owner_key] = {"pid": 999999999, "start": "0", "boot": "old-boot"}
            self.pool.recover()
            self.assertEqual(self.pool.status()[lease["slot"] - 1]["state"], "quarantined")
        self.assertEqual(self.resources.dropped, [])


class PostgresAdapterTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertTrue(hasattr(self.m, "Postgres"), "managed PostgreSQL adapter is missing")
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-slot-pg-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.resources = Resources()
        self.pool = self.m.Pool(self.root / "pool", self.m.newyou_contract(), self.resources, approval_check=approve_for_test)
        self.pool.enable(self.pool.manifest_digest(), "synthetic-approval")
        self.lease = self.pool.acquire(str(self.root))
        self.statements = []
        self.catalog = {"database_oid": 1001, "role_oid": 2001, "owner_oid": 10, "admin_oid": 10,
                        "database_comment": self.m.ownership_comment(self.lease),
                        "role_comment": self.m.ownership_comment(self.lease),
                        "clients": 0, "privileged": False, "memberships": 0, "other_databases": 0}
        self.adapter = self.m.Postgres(self.m.newyou_contract(), lambda row: "synthetic_password",
                                      executor=self.sql, endpoint=lambda: "a" * 64)

    def sql(self, statement):
        self.statements.append(statement)
        if "json_build_object" in statement:
            return json.dumps(self.catalog)
        if "aclexplode" in statement:
            return "f"
        if "EXISTS" in statement and "pg_database" in statement:
            return "f"
        if "count(*)" in statement:
            return "0"
        return ""

    def test_prepare_uses_only_new_exact_targets_and_restricted_roles(self):
        catalog = self.adapter.prepare(self.lease)
        sql = "\n".join(self.statements)
        self.assertIn("NOCREATEDB", sql)
        self.assertIn("NOSUPERUSER", sql)
        self.assertIn("NOCREATEROLE", sql)
        self.assertIn("NOBYPASSRLS", sql)
        self.assertIn("REVOKE ALL", sql)
        self.assertIn("ALLOW_CONNECTIONS false", sql)
        self.assertNotIn("ALTER ROLE new_you_test", sql)
        self.assertEqual(catalog["container_id"], "a" * 64)

    def test_runtime_cannot_own_database_or_delegate_connection_privileges(self):
        self.adapter.prepare(self.lease)
        sql = "\n".join(self.statements)
        self.assertIn(f"CREATE DATABASE {self.lease['database']} OWNER devcore_admin", sql)
        self.assertIn(f"GRANT CONNECT, TEMPORARY ON DATABASE {self.lease['database']} TO {self.lease['role']}", sql)
        self.assertIn(f"GRANT USAGE, CREATE ON SCHEMA public TO {self.lease['role']}", sql)
        self.assertNotIn("WITH GRANT OPTION", sql)

    def test_runtime_database_ownership_is_rejected_before_cleanup_mutations(self):
        self.lease["catalog"]["container_id"] = "a" * 64
        self.catalog["admin_oid"] = 10
        self.catalog["owner_oid"] = self.catalog["role_oid"]
        with self.assertRaises(self.m.SlotError):
            self.adapter.cleanup(self.lease)
        self.assertFalse(any("DROP " in x or "ALTER " in x for x in self.statements))

    def test_changed_administrative_owner_oid_cannot_authorize_cleanup(self):
        self.lease["catalog"].update(container_id="a" * 64, owner_oid=10)
        self.catalog.update(owner_oid=20, admin_oid=20)
        with self.assertRaises(self.m.SlotError):
            self.adapter.cleanup(self.lease)
        self.assertFalse(any("DROP " in x or "ALTER " in x for x in self.statements))

    def test_existing_identity_is_never_adopted(self):
        self.adapter.executor = lambda sql: "t"
        with self.assertRaisesRegex(self.m.SlotError, "already exists"):
            self.adapter.prepare(self.lease)

    def test_legacy_public_connect_or_uncertain_acl_blocks_before_credentials_or_creation(self):
        from unittest.mock import Mock
        for result in ("t", "", "unexpected"):
            with self.subTest(result=result):
                self.statements.clear()
                password = Mock(return_value="synthetic_password")
                self.adapter.password = password
                def sql(statement):
                    if "aclexplode" in statement:
                        self.statements.append(statement)
                        return result
                    return self.sql(statement)
                self.adapter.executor = sql
                with self.assertRaisesRegex(self.m.SlotError, "legacy TEST.*CONNECT"):
                    self.adapter.prepare(self.lease)
                password.assert_not_called()
                self.assertFalse(any("CREATE " in x or "ALTER " in x or "REVOKE " in x
                                     for x in self.statements))

    def test_legacy_acl_guard_reads_effective_public_connect_without_mutating_it(self):
        self.adapter.prepare(self.lease)
        guard = next((x for x in self.statements if "aclexplode" in x), "")
        self.assertIn("acldefault('d', datdba)", guard)
        self.assertIn("grantee=0", guard)
        self.assertIn("privilege_type='CONNECT'", guard)
        self.assertIn("datname='new_you_test'", guard)
        self.assertNotIn("REVOKE", guard)

    def test_catalog_oids_have_numeric_json_types_at_postgres_boundary(self):
        def postgres_json(statement):
            if "json_build_object" in statement:
                row = self.catalog.copy()
                for key, expression in (("database_oid", "d.oid::bigint"),
                                        ("role_oid", "r.oid::bigint"),
                                        ("owner_oid", "d.datdba::bigint"),
                                        ("admin_oid", "a.oid::bigint")):
                    # PostgreSQL emits built-in OID as JSON text. Explicit int8
                    # casts preserve the strict numeric metadata contract.
                    if expression not in statement:
                        row[key] = str(row[key])
                return json.dumps(row)
            return self.sql(statement)
        self.adapter.executor = postgres_json
        catalog = self.adapter.prepare(self.lease)
        self.assertIs(type(catalog["database_oid"]), int)
        self.assertIs(type(catalog["role_oid"]), int)

    def test_cleanup_checks_exact_catalog_and_never_forces(self):
        self.lease["catalog"]["container_id"] = "a" * 64
        self.lease["catalog"]["owner_oid"] = 10
        self.adapter.cleanup(self.lease)
        sql = "\n".join(self.statements)
        self.assertIn("DROP DATABASE", sql)
        self.assertIn("ALLOW_CONNECTIONS false", sql)
        self.assertIn("NOLOGIN", sql)
        self.assertNotIn("FORCE", sql)
        self.assertNotIn("pg_terminate_backend", sql)

    def test_cleanup_rejects_every_ownership_mismatch_before_mutation(self):
        self.lease["catalog"]["container_id"] = "a" * 64
        self.lease["catalog"]["owner_oid"] = 10
        for key, bad in (("database_oid", 9), ("role_oid", 9), ("owner_oid", 9),
                         ("admin_oid", 9),
                         ("database_comment", "foreign"), ("role_comment", "foreign"),
                         ("clients", 1), ("privileged", True), ("memberships", 1), ("other_databases", 1)):
            with self.subTest(key=key):
                old = self.catalog[key]
                self.catalog[key] = bad
                self.statements.clear()
                with self.assertRaises(self.m.SlotError):
                    self.adapter.cleanup(self.lease)
                self.assertFalse(any("DROP " in x or "ALTER " in x for x in self.statements))
                self.catalog[key] = old

    def test_protected_names_and_endpoint_replacement_are_rejected(self):
        for database in ("new_you_dev", "new_you_test", "postgres", "template0", "template1", "dc_new_you_s01_unregistered"):
            row = copy.deepcopy(self.lease)
            row["database"] = database
            with self.assertRaises(self.m.SlotError):
                self.adapter.prepare(row)
            self.assertEqual(self.statements, [])
        self.lease["catalog"]["container_id"] = "b" * 64
        with self.assertRaises(self.m.SlotError):
            self.adapter.cleanup(self.lease)
        self.assertEqual(self.statements, [])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertTrue(hasattr(self.m, "managed_run"), "managed command supervisor is missing")
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-slot-command-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.pool = self.m.Pool(self.root / "pool", self.m.newyou_contract(), Resources(),
                                port_available=lambda _: True, approval_check=approve_for_test)
        self.pool.enable(self.pool.manifest_digest(), "synthetic-approval")
        self.lease = self.pool.acquire(str(self.root))

    def test_command_inherits_identity_and_success_cleans_only_its_generation(self):
        output = self.root / "observed.json"
        command = ["python3", "-c", "import os,json,sys;json.dump({k:os.getenv(k) for k in "
                   "['DEVCORE_SLOT_LEASE','DEVCORE_SLOT_GENERATION','DEVCORE_SLOT_JOB','NEW_YOU_PORT']},open(sys.argv[1],'w'))", str(output)]
        code = self.m.managed_run(self.pool, self.lease, command, os.environ.copy())
        self.assertEqual(code, 0)
        row = json.loads(output.read_text())
        self.assertEqual(row["DEVCORE_SLOT_LEASE"], self.lease["lease_id"])
        self.assertEqual(row["DEVCORE_SLOT_GENERATION"], self.lease["generation"])
        self.assertEqual(row["NEW_YOU_PORT"], str(self.lease["port"]))
        self.assertTrue(row["DEVCORE_SLOT_JOB"])
        self.assertEqual(self.pool.status()[0]["state"], "free")

    def test_console_forwarding_retries_short_writes_and_rejects_zero_progress(self):
        from unittest.mock import patch
        received = bytearray()
        def short_write(fd, data):
            self.assertEqual(fd, 123)
            count = min(3, len(data))
            received.extend(data[:count])
            return count
        with patch.object(self.m.os, "write", side_effect=short_write):
            self.m.write_all(123, b"complete synthetic output")
        self.assertEqual(received, b"complete synthetic output")
        with patch.object(self.m.os, "write", return_value=0):
            with self.assertRaises(OSError):
                self.m.write_all(123, b"output")

    def test_failing_command_retains_redacted_diagnosis(self):
        code = self.m.managed_run(self.pool, self.lease,
                                 ["python3", "-c", "import sys;print('synthetic_secret');sys.exit(7)"],
                                 os.environ.copy(), redact=["synthetic_secret"])
        self.assertEqual(code, 7)
        row = self.pool.status()[0]
        self.assertEqual(row["state"], "retained")
        output = next((self.pool.root / "runs").glob("*/output.log"))
        self.assertNotIn("synthetic_secret", output.read_text())
        self.assertIn("[REDACTED]", output.read_text())

    def test_supervisor_waits_for_orphan_grandchild(self):
        output = self.root / "late-child"
        # Exercise subreaping in a separate supervisor process, not in the unittest runner.
        runner = self.root / "run.py"
        runner.write_text("from pathlib import Path\nimport types,os\n"
            f"source=Path({str(TOOL)!r}).read_text().split({BEGIN!r},1)[1].split({END!r},1)[0]\n"
            "m=types.ModuleType('slots');exec(source,m.__dict__)\n"
            f"pool=m.Pool(Path({str(self.pool.root)!r}),m.newyou_contract(),None)\n"
            f"lease=pool.status()[0]\n"
            f"command=['python3','-c',\"import os,time;pid=os.fork();"
            f"os._exit(0) if pid else None;os.setsid();time.sleep(0.15);open({str(output)!r},'w').write('done')\"]\n"
            "raise SystemExit(m.managed_run(pool,lease,command,os.environ.copy(),auto_release=False,heavy=True))\n")
        result = subprocess.run(["python3", str(runner)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.exists())
        self.assertEqual(self.pool.status()[0]["state"], "ready")

    def test_prelaunch_port_conflict_retains_releasable_database_without_touching_listener(self):
        with socket.socket() as held:
            held.bind(("127.0.0.1", self.lease["port"]))
            with self.assertRaises(self.m.SlotError):
                self.m.managed_run(self.pool, self.lease, ["true"], os.environ.copy())
            row = self.pool.status()[0]
            self.assertEqual(row["state"], "retained")
            self.assertEqual(row["jobs"], {})
            self.assertIn("before launch", row["diagnosis"])
            self.pool.release(self.lease["lease_id"], self.lease["generation"], str(self.root))
            self.assertEqual(self.pool.status()[0]["state"], "free")
            self.assertEqual(held.getsockname(), ("127.0.0.1", self.lease["port"]))

    def test_second_run_port_conflict_cannot_change_an_active_job(self):
        job = self.pool.begin_job(self.lease["lease_id"], self.lease["generation"], str(self.root))
        with socket.socket() as held:
            held.bind(("127.0.0.1", self.lease["port"]))
            with self.assertRaises(self.m.SlotError):
                self.m.managed_run(self.pool, self.lease, ["true"], os.environ.copy())
            row = self.pool.status()[0]
            self.assertEqual(row["state"], "in_use")
            self.assertEqual(set(row["jobs"]), {job})
            self.assertEqual(self.pool.resources.dropped, [])

    def test_missing_kernel_pidfd_support_fails_before_job_launch(self):
        from unittest.mock import patch
        import errno
        with patch.object(self.m.os, "pidfd_open", side_effect=OSError(errno.ENOSYS, "synthetic unsupported kernel")):
            with self.assertRaisesRegex(self.m.SlotError, "pidfd"):
                self.m.managed_run(self.pool, self.lease, ["true"], os.environ.copy())
        self.assertEqual(self.pool.status()[0]["jobs"], {})

    def test_term_stops_owned_orphan_after_launcher_exit_and_preserves_unknown_process(self):
        import signal
        import time
        ready, stopped = self.root / "signal-ready", self.root / "signal-stopped"
        child_script = self.root / "signal-child.py"
        child_script.write_text("import os,signal,time\n"
            "pid=os.fork()\nif pid: os._exit(0)\nos.setsid()\n"
            f"def stop(*_):\n    open({str(stopped)!r},'w').write('term')\n    raise SystemExit(0)\n"
            "signal.signal(signal.SIGTERM,stop)\n"
            f"open({str(ready)!r},'w').write(str(os.getpid()))\ntime.sleep(10)\n")
        runner = self.root / "signal-runner.py"
        runner.write_text("from pathlib import Path\nimport types,os\n"
            f"source=Path({str(TOOL)!r}).read_text().split({BEGIN!r},1)[1].split({END!r},1)[0]\n"
            "m=types.ModuleType('slots');exec(source,m.__dict__)\n"
            f"pool=m.Pool(Path({str(self.pool.root)!r}),m.newyou_contract(),None)\n"
            "lease=pool.status()[0]\n"
            f"raise SystemExit(m.managed_run(pool,lease,['python3',{str(child_script)!r}],os.environ.copy(),auto_release=False))\n")
        unknown = subprocess.Popen(["python3", "-c", "import time;time.sleep(10)"])
        process = subprocess.Popen(["python3", str(runner)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owned_identity = None
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            owned_identity = self.m.process_identity(int(ready.read_text()))
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=2), 0)
            self.assertTrue(stopped.exists())
            self.assertIsNone(unknown.poll())
            self.assertEqual(self.pool.status()[0]["state"], "ready")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            if owned_identity and self.m.process_alive(owned_identity):
                try:
                    fd = os.pidfd_open(owned_identity["pid"])
                    try:
                        if self.m.process_alive(owned_identity):
                            signal.pidfd_send_signal(fd, signal.SIGTERM)
                    finally:
                        os.close(fd)
                except ProcessLookupError:
                    pass
            unknown.terminate()
            unknown.wait(timeout=2)

    def test_known_prelaunch_failures_do_not_strand_heavy_permits(self):
        from unittest.mock import patch
        with socket.socket() as held:
            held.bind(("127.0.0.1", self.lease["port"]))
            with self.assertRaises(self.m.SlotError):
                self.m.managed_run(self.pool, self.lease, ["true"], os.environ.copy(), heavy=True)
        receipts = list((self.pool.root / "heavy").glob("*.json"))
        self.assertTrue(receipts)
        self.assertTrue(all(json.loads(path.read_text())["state"] == "free" for path in receipts))
        lease = self.pool.acquire(str(self.root))
        with patch.object(self.m.subprocess, "Popen", side_effect=OSError("synthetic launch failure")):
            with self.assertRaises(OSError):
                self.m.managed_run(self.pool, lease, ["true"], os.environ.copy(), heavy=True)
        self.assertTrue(all(json.loads(path.read_text())["state"] == "free" for path in receipts))
        row = next(row for row in self.pool.status() if row["lease_id"] == lease["lease_id"])
        self.assertEqual(row["state"], "retained")
        self.assertEqual(row["jobs"], {})

    def test_listener_checks_are_bounded_and_foreign_handoff_quarantines(self):
        from unittest.mock import patch
        calls = []
        with patch.object(self.m, "listener_ownership", side_effect=lambda *_: calls.append(1) or "absent"):
            self.assertEqual(self.m.managed_run(self.pool, self.lease,
                ["python3", "-c", "import time;time.sleep(0.6)"], os.environ.copy(),
                http=True, auto_release=False), 0)
        self.assertGreaterEqual(len(calls), 2)
        self.assertLessEqual(len(calls), 4)
        with patch.object(self.m, "listener_ownership", return_value="foreign"):
            self.assertEqual(self.m.managed_run(self.pool, self.lease, ["true"],
                os.environ.copy(), http=True, auto_release=False), 0)
        self.assertEqual(self.pool.status()[0]["state"], "quarantined")

    def test_cli_has_opt_in_commands_without_changing_installed_tool(self):
        result = subprocess.run([str(TOOL), "slots", "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("manifest", result.stdout)
        self.assertIn("recover", result.stdout)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        from tests.test_devcore import DevCoreProjectFixture
        from unittest.mock import patch
        self.fixture = DevCoreProjectFixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.m = module()
        f = self.fixture
        conf = f.project / ".devcore/project.conf"
        conf.write_text(conf.read_text().replace("demo", "new_you").replace("DEMO", "NEW_YOU").replace("TEST_ROLE_CREATEDB=yes", "TEST_ROLE_CREATEDB=no") + "SLOT_POOL=.devcore/slots.json\n")
        f.secrets.write_text(f.secrets.read_text().replace("DEMO", "NEW_YOU"))
        global_text = f.global_conf.read_text().replace("PG_TEST_CONTAINER=devcore-test-test", "PG_TEST_CONTAINER=dev-core-postgres-test-1")
        global_text = global_text.replace("PG_ADMIN_ROLE=devcore_test_admin", "PG_ADMIN_ROLE=devcore_admin")
        f.global_conf.write_text(global_text)
        (f.project / ".devcore/slots.json").write_text(json.dumps(self.m.newyou_contract()))
        self.patch = patch.dict(os.environ, f.env(), clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.old_cwd = os.getcwd()
        os.chdir(f.project)
        self.addCleanup(os.chdir, self.old_cwd)
        self.context = self.m.SlotContext(str(TOOL), conf, f.global_conf, f.secrets, f.central)
        self.context.pool.resources = Resources()
        self.context.pool.approval_check = approve_for_test
        self.context.pool.enable(self.context.pool.manifest_digest(), "synthetic-approval")
        self.lease = self.context.pool.acquire(str(f.project))
        with f.secrets.open("a") as stream:
            stream.write(self.context.secrets.key(self.lease) + "=" + "a" * 64 + "\n")

    def test_existing_renderer_gets_private_per_command_snapshots(self):
        before = self.fixture.secrets.read_bytes()
        env = self.context.environment(self.lease, "test")
        self.assertEqual(env["TEST_DATABASE_NAME"], self.lease["database"])
        self.assertEqual(env["TEST_DATABASE_USERNAME"], self.lease["role"])
        self.assertEqual(env["TEST_DATABASE_PASSWORD"], "a" * 64)
        self.assertNotIn("DEV_DATABASE_PASSWORD", env)
        self.assertEqual(env["MIX_ENV"], "test")
        self.assertEqual(self.fixture.secrets.read_bytes(), before)
        self.assertFalse((self.fixture.project / ".env.test").exists())
        first = set((self.context.pool.root / "snapshots").iterdir())
        self.context.environment(self.lease, "test")
        second = set((self.context.pool.root / "snapshots").iterdir())
        self.assertEqual(first, set(), "secret snapshots must be removed after loading")
        self.assertEqual(second, set())

    def test_dev_environment_preserves_shared_dev_and_supplies_isolated_test_for_children(self):
        env = self.context.environment(self.lease, "dev")
        self.assertEqual(env["DEV_DATABASE_NAME"], "new_you_dev")
        self.assertEqual(env["TEST_DATABASE_NAME"], self.lease["database"])
        self.assertEqual(env["MIX_ENV"], "dev")

    def test_arbitrary_parent_pg_values_and_build_overrides_fail_closed(self):
        os.environ.update(DATABASE_URL="ignored-parent-value", PGDATABASE="new_you_test")
        env = self.context.environment(self.lease, "test")
        self.assertNotIn("DATABASE_URL", env)
        self.assertNotIn("PGDATABASE", env)
        os.environ["MIX_BUILD_PATH"] = "/tmp/shared-build"
        with self.assertRaises(self.m.SlotError):
            self.context.environment(self.lease, "test")
        os.environ.pop("MIX_BUILD_PATH")
        os.environ["MIX_TEST_PARTITION"] = "1"
        with self.assertRaises(self.m.SlotError):
            self.context.environment(self.lease, "test")

    def test_live_child_verifier_and_nested_compatible_run(self):
        env = self.context.environment(self.lease, "test")
        output = self.fixture.root / "verified.json"
        child = ["python3", "-c", "import os,subprocess,sys;result=subprocess.run([sys.argv[1],'slots','verify','--lease',os.environ['DEVCORE_SLOT_LEASE'],'--generation',os.environ['DEVCORE_SLOT_GENERATION'],'--job',os.environ['DEVCORE_SLOT_JOB']],capture_output=True,text=True);open(sys.argv[2],'w').write(result.stdout);sys.exit(result.returncode)", str(TOOL), str(output)]
        self.assertEqual(self.m.managed_run(self.context.pool, self.lease, child, env, auto_release=False), 0)
        self.assertEqual(json.loads(output.read_text())["database"], self.lease["database"])
        self.assertEqual(self.context.pool.status()[0]["state"], "ready")

    def test_verifier_rejects_non_child_and_stale_identity(self):
        with self.assertRaises(self.m.SlotError):
            self.m.verify_job(self.context.pool, self.lease["lease_id"], self.lease["generation"], "absent", str(self.fixture.project))

    def test_valid_local_build_override_is_preserved(self):
        os.environ["MIX_BUILD_PATH"] = str(self.fixture.project / "alternate-build")
        env = self.context.environment(self.lease, "test")
        self.assertEqual(env["MIX_BUILD_PATH"], os.environ["MIX_BUILD_PATH"])

    def test_secret_generation_does_not_touch_existing_credentials_or_use_argv(self):
        row = dict(self.lease, generation="b" * 32)
        before = self.fixture.secrets.read_text()
        password = self.context.secrets.create(row)
        self.assertEqual(len(password), 64)
        self.assertTrue(self.fixture.secrets.read_text().startswith(before))
        self.assertEqual(self.context.secrets.existing(row), password)
        with self.assertRaises(self.m.SlotError):
            self.context.secrets.create(row)


    def test_environment_setup_errors_retain_exact_automatic_lease(self):
        from unittest.mock import patch
        errors = (subprocess.TimeoutExpired("synthetic-renderer", 1), OSError("synthetic setup failure"), KeyboardInterrupt())
        for error in errors:
            with self.subTest(error=type(error).__name__):
                previous = {row["lease_id"] for row in self.context.pool.status()}
                with patch.object(self.m, "SlotContext", return_value=self.context), \
                     patch.object(self.context, "environment", side_effect=error):
                    with self.assertRaises(type(error)):
                        self.m.slot_cli(["run", "test", "--", "true"])
                acquired = [row for row in self.context.pool.status() if row["lease_id"] not in previous]
                self.assertEqual(len(acquired), 1)
                self.assertEqual(acquired[0]["state"], "retained")
                self.assertEqual(acquired[0]["jobs"], {})

    def test_nested_run_rebuilds_database_binding_and_cannot_escalate_test_to_dev(self):
        output = self.fixture.root / "nested-observed.json"
        script = """import os,sys,subprocess,json
os.environ.update(TEST_DATABASE_NAME='new_you_test',TEST_DATABASE_USERNAME='new_you_test',
                  DATABASE_URL='postgres://unrelated',PGDATABASE='new_you_dev',
                  DEV_DATABASE_PASSWORD='forged',MIX_ENV='dev',DEVCORE_SLOT_PROJECT='forged',\n                  DEVCORE_SLOT_WORKTREE='/tmp/forged',NEW_YOU_PORT='4220')
code='import os,json;print(json.dumps({k:os.environ.get(k) for k in ["TEST_DATABASE_NAME","TEST_DATABASE_USERNAME","DATABASE_URL","PGDATABASE","DEV_DATABASE_PASSWORD","DEVCORE_SLOT_JOB","DEVCORE_SLOT_PROJECT","DEVCORE_SLOT_WORKTREE","NEW_YOU_PORT"]}))'
test=subprocess.run([sys.argv[1],'run','test','--','python3','-c',code],capture_output=True,text=True)
dev=subprocess.run([sys.argv[1],'run','dev','--','true'],capture_output=True,text=True)
generation=os.environ['DEVCORE_SLOT_GENERATION']
os.environ['DEVCORE_SLOT_GENERATION']='0'*32
stale=subprocess.run([sys.argv[1],'run','test','--','true'],capture_output=True,text=True)
os.environ['DEVCORE_SLOT_GENERATION']=generation
os.environ.pop('DEVCORE_SLOT_JOB')
partial=subprocess.run([sys.argv[1],'run','test','--','true'],capture_output=True,text=True)
json.dump({'test_exit':test.returncode,'env':json.loads(test.stdout),'dev_exit':dev.returncode,
           'stale_exit':stale.returncode,'partial_exit':partial.returncode},open(sys.argv[2],'w'))
"""
        env = self.context.environment(self.lease, "test")
        self.assertEqual(self.m.managed_run(self.context.pool, self.lease,
            ["python3", "-c", script, str(TOOL), str(output)], env, auto_release=False), 0)
        observed = json.loads(output.read_text())
        self.assertEqual(observed["test_exit"], 0)
        self.assertEqual(observed["env"]["TEST_DATABASE_NAME"], self.lease["database"])
        self.assertEqual(observed["env"]["TEST_DATABASE_USERNAME"], self.lease["role"])
        for key in ("DATABASE_URL", "PGDATABASE", "DEV_DATABASE_PASSWORD"):
            self.assertIsNone(observed["env"][key])
        self.assertTrue(observed["env"]["DEVCORE_SLOT_JOB"])
        self.assertNotEqual(observed["dev_exit"], 0)
        self.assertNotEqual(observed["stale_exit"], 0)
        self.assertNotEqual(observed["partial_exit"], 0)
        self.assertEqual(observed["env"]["DEVCORE_SLOT_PROJECT"], "new_you")
        self.assertEqual(observed["env"]["DEVCORE_SLOT_WORKTREE"], str(self.fixture.project.resolve()))
        self.assertEqual(observed["env"]["NEW_YOU_PORT"], str(self.lease["port"]))

    def test_managed_markers_cannot_fall_back_through_a_legacy_declaration(self):
        legacy = self.fixture.project / ".devcore/legacy.conf"
        legacy.write_text(Path(self.context.project_file).read_text().replace("SLOT_POOL=.devcore/slots.json\n", ""))
        (self.fixture.project / ".env.test").write_text("TEST_DATABASE_NAME=new_you_test\n")
        env = self.fixture.env()
        env.update(DEVCORE_PROJECT_CONF=str(legacy), DEVCORE_SLOT_JOB="synthetic-job")
        result = subprocess.run([str(TOOL), "run", "test", "--", "true"],
                                cwd=self.fixture.project, env=env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has not opted in", result.stderr)

    def test_rendered_database_aliases_are_rejected_after_merge(self):
        # Resolve the fixture's actual TEST template rather than assuming a name.
        row = next(line.split("\t") for line in (self.fixture.project / ".devcore/render-map.tsv").read_text().splitlines() if line.startswith("test\t"))
        template = self.fixture.project / row[1]
        original = template.read_text()
        for variable in ("DATABASE_URL", "PGDATABASE", "TEST_DATABASE_URL", "DATABASE_URL_TEST",
                         "TEST_DB_URL", "DB_URL", "TEST_DATABASE_HOSTNAME"):
            with self.subTest(variable=variable):
                template.write_text(original + f"\n{variable}=unrelated\n")
                with self.assertRaisesRegex(self.m.SlotError, "alternate database"):
                    self.context.environment(self.lease, "test")
        template.write_text(original)

    def test_rendered_partition_is_rejected_before_managed_launch(self):
        rows = [line.split("\t") for line in (self.fixture.project / ".devcore/render-map.tsv").read_text().splitlines()]
        for profile in ("test", "dev"):
            with self.subTest(profile=profile):
                row = next(row for row in rows if row[0] == profile)
                template = self.fixture.project / row[1]
                original = template.read_text()
                try:
                    template.write_text(original + "\nMIX_TEST_PARTITION=2\n")
                    with self.assertRaisesRegex(self.m.SlotError, "MIX_TEST_PARTITION"):
                        self.context.environment(self.lease, profile)
                finally:
                    template.write_text(original)
        self.assertEqual(list((self.context.pool.root / "snapshots").iterdir()), [])

    def test_supplemental_partition_is_rejected_after_binding(self):
        mapping = self.fixture.project / ".devcore/supplemental.tsv"
        mapping.write_text("all\tMIX_TEST_PARTITION\tSYNTHETIC_PARTITION\n")
        with self.fixture.secrets.open("a") as stream:
            stream.write("SYNTHETIC_PARTITION=2\n")
        self.context.project["SUPPLEMENTAL_SECRETS"] = str(mapping)
        for profile in ("test", "dev"):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(self.m.SlotError, "MIX_TEST_PARTITION"):
                    self.context.environment(self.lease, profile)
        self.assertEqual(list((self.context.pool.root / "snapshots").iterdir()), [])

    def test_inherited_database_url_aliases_cannot_survive_managed_merge(self):
        for variable in ("DATABASE_URL_TEST", "TEST_DB_URL", "DB_URL"):
            with self.subTest(variable=variable):
                os.environ[variable] = "synthetic-legacy"
                try:
                    with self.assertRaisesRegex(self.m.SlotError, "alternate database"):
                        self.context.environment(self.lease, "test")
                finally:
                    os.environ.pop(variable)

    def test_supplemental_profiles_purge_inheritance_and_apply_without_template_tokens(self):
        f = self.fixture
        mapping = f.project / ".devcore/supplemental.tsv"
        mapping.write_text("dev\tDEV_ONLY_TOKEN\tSYNTHETIC_DEV_TOKEN\n"
                           "test\tTEST_ONLY_TOKEN\tSYNTHETIC_TEST_TOKEN\n"
                           "all\tCOMMON_TOKEN\tSYNTHETIC_COMMON_TOKEN\n")
        with f.secrets.open("a") as stream:
            stream.write("SYNTHETIC_DEV_TOKEN=synthetic-dev\nSYNTHETIC_TEST_TOKEN=synthetic-test\nSYNTHETIC_COMMON_TOKEN=synthetic-common\n")
        self.context.project["SUPPLEMENTAL_SECRETS"] = str(mapping)
        row = next(line.split("\t") for line in (f.project / ".devcore/render-map.tsv").read_text().splitlines() if line.startswith("test\t"))
        template = f.project / row[1]
        template.write_text(template.read_text() + "\nTEST_ONLY_TOKEN={{TEST_ONLY_TOKEN}}\n")
        os.environ.update(DEV_ONLY_TOKEN="wrong-inherited-dev", TEST_ONLY_TOKEN="wrong-inherited-test")
        dev = self.context.environment(self.lease, "dev")
        test = self.context.environment(self.lease, "test")
        self.assertEqual(dev.get("DEV_ONLY_TOKEN"), "synthetic-dev")
        self.assertNotIn("TEST_ONLY_TOKEN", dev)
        self.assertEqual(test.get("TEST_ONLY_TOKEN"), "synthetic-test")
        self.assertNotIn("DEV_ONLY_TOKEN", test)
        self.assertEqual(dev.get("COMMON_TOKEN"), "synthetic-common")
        self.assertEqual(test.get("COMMON_TOKEN"), "synthetic-common")

    def test_managed_all_profile_is_rejected_without_acquiring_or_using_shared_test(self):
        before_registry = (self.context.pool.root / "registry.json").read_bytes()
        before_secrets = self.fixture.secrets.read_bytes()
        result = subprocess.run([str(TOOL), "run", "all", "--", "true"],
                                cwd=self.fixture.project, env=self.fixture.env(),
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed mode supports only dev and test; run all is unavailable", result.stderr)
        self.assertEqual((self.context.pool.root / "registry.json").read_bytes(), before_registry)
        self.assertEqual(self.fixture.secrets.read_bytes(), before_secrets)

    def test_automatic_cli_and_nested_run_keep_managed_identity_and_stdin(self):
        f = self.fixture
        docker = f.mock_bin / "docker"
        docker.write_text("#!/usr/bin/env python3\n" + r'''
import hashlib,json,os,sys
from pathlib import Path
args=sys.argv[1:]
if args[0]=='inspect':
    print('a'*64 if '{{.Id}}' in args else 'true')
elif args[0]=='port':
    print('127.0.0.1:55433')
elif args[0]=='exec':
    sql=sys.stdin.read()
    if 'json_build_object' in sql:
        rows=json.loads(Path(os.environ['MOCK_SLOT_REGISTRY']).read_text())['slots'].values()
        row=next(row for row in rows if row['database'] in sql)
        comment='devcore-slot:v1:new_you:'+row['lease_id']+':'+row['generation']+':'+hashlib.sha256(row['worktree'].encode()).hexdigest()+':'+row['manifest']
        print(json.dumps(dict(database_oid=1000+row['slot'],role_oid=2000+row['slot'],owner_oid=10,admin_oid=10,database_comment=comment,role_comment=comment,clients=0,privileged=False,memberships=0,other_databases=0)))
    elif 'EXISTS' in sql:
        print('f')
else:
    sys.exit(1)
''')
        docker.chmod(0o700)
        env = f.env()
        env.update(PATH=str(f.mock_bin) + os.pathsep + os.environ['PATH'],
                   MOCK_SLOT_REGISTRY=str(self.context.pool.root / "registry.json"))
        output = f.root / "automatic.json"
        script = ("import os,sys,json,subprocess; "
                  "observed={'database':os.environ['TEST_DATABASE_NAME'],'stdin':sys.stdin.read()}; "
                  "nested=subprocess.run([sys.argv[1],'run','test','--','python3','-c',"
                  "'import os;print(os.environ[\"TEST_DATABASE_NAME\"])'],capture_output=True,text=True); "
                  "observed['nested']=nested.stdout.strip();observed['nested_exit']=nested.returncode; "
                  "json.dump(observed,open(sys.argv[2],'w'))")
        result = subprocess.run([str(TOOL), "run", "test", "--", "python3", "-c", script, str(TOOL), str(output)],
                                cwd=f.project, env=env, input="synthetic-stdin", capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(output.read_text())
        self.assertNotEqual(observed["database"], "new_you_test")
        self.assertEqual(observed["nested"], observed["database"])
        self.assertEqual(observed["nested_exit"], 0)
        self.assertEqual(observed["stdin"], "synthetic-stdin")
        self.assertEqual(self.context.pool.status()[1]["state"], "free")


class ActivationTests(unittest.TestCase):
    def test_reviewable_manifest_matches_source_without_activating_anything(self):
        m = module()
        requested = json.loads((ROOT / "docs/activation/newyou-workstation-manifest.json").read_text())
        pool = m.Pool.__new__(m.Pool)
        pool.root = Path(requested["manifest"]["registry"])
        pool.contract = m.newyou_contract()
        self.assertEqual(requested["manifest"], pool.manifest())
        self.assertEqual(requested["sha256"], pool.manifest_digest())
        self.assertEqual(requested["authorization_status"], "NOT_AUTHORIZED")

    def test_local_reference_is_not_owner_authorization(self):
        m = module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            pool = m.Pool(root / "pool", m.newyou_contract(), Resources())
            with self.assertRaisesRegex(m.SlotError, "owner"):
                pool.enable(pool.manifest_digest(), "self-issued-reference")

    def test_postgres_sql_uses_the_inspected_container_id(self):
        from unittest.mock import patch
        m = module()
        adapter = m.Postgres(m.newyou_contract(), lambda row: "synthetic")
        adapter.bound_container = "a" * 64
        observed = []
        def run(args, **kwargs):
            observed.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch.object(m.subprocess, "run", run):
            adapter.execute("SELECT 1;")
        self.assertEqual(observed[0][3], "a" * 64)


def claim_in_process(arguments):
    root, worktree = arguments
    m = module()
    pool = m.Pool(Path(root), m.newyou_contract(), Resources(), port_available=lambda _: True)
    return pool.acquire(worktree)


class MultiprocessTests(unittest.TestCase):
    def test_twenty_processes_from_distinct_worktrees_claim_once(self):
        import multiprocessing
        m = module()
        with tempfile.TemporaryDirectory(prefix="devcore-20-claims-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            pool = m.Pool(root / "pool", m.newyou_contract(), Resources(),
                          port_available=lambda _: True, approval_check=approve_for_test)
            pool.enable(pool.manifest_digest(), "synthetic-owner-approval")
            worktrees = [root / f"worktree-{i}" for i in range(20)]
            for path in worktrees:
                path.mkdir()
            with concurrent.futures.ProcessPoolExecutor(max_workers=20,
                    mp_context=multiprocessing.get_context("fork")) as executor:
                leases = list(executor.map(claim_in_process, [(str(pool.root), str(path)) for path in worktrees]))
            for key in ("slot", "port", "database", "role", "lease_id", "generation", "worktree"):
                self.assertEqual(len({row[key] for row in leases}), 20, key)
            self.assertTrue(all(row["state"] == "ready" for row in pool.status()))

    def test_killed_supervisor_leaves_live_child_and_quarantines(self):
        import signal
        import time
        m = module()
        with tempfile.TemporaryDirectory(prefix="devcore-supervisor-loss-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            pool = m.Pool(root / "pool", m.newyou_contract(), Resources(),
                          port_available=lambda _: True, approval_check=approve_for_test)
            pool.enable(pool.manifest_digest(), "synthetic-owner-approval")
            lease = pool.acquire(str(root))
            marker, started = root / "child-survived", root / "child-started"
            runner = root / "runner.py"
            runner.write_text("from pathlib import Path\nimport types,os\n"
                f"source=Path({str(TOOL)!r}).read_text().split({BEGIN!r},1)[1].split({END!r},1)[0]\n"
                "m=types.ModuleType('slots');exec(source,m.__dict__)\n"
                f"pool=m.Pool(Path({str(pool.root)!r}),m.newyou_contract(),None)\n"
                "lease=pool.status()[0]\n"
                f"command=['python3','-c',\"import time;open({str(started)!r},'w').close();time.sleep(0.4);open({str(marker)!r},'w').write('alive')\"]\n"
                "m.managed_run(pool,lease,command,os.environ.copy(),auto_release=False,heavy=True)\n")
            process = subprocess.Popen(["python3", str(runner)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 5
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(started.exists())
                process.send_signal(signal.SIGKILL)
                process.wait(timeout=2)
                pool.recover()
                self.assertEqual(pool.status()[0]["state"], "quarantined")
                with self.assertRaises(m.SlotError):
                    pool.release(lease["lease_id"], lease["generation"], str(root))
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "supervisor loss must not terminate a live child")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)


class OwnerApprovalTests(unittest.TestCase):
    def test_heavy_detection_includes_full_suite_flags_but_excludes_focused_tests(self):
        m = module()
        self.assertTrue(hasattr(m, "is_heavy_command"), "automatic heavy command classification is missing")
        for command in (["mix", "check"], ["mix", "check.deep"], ["mix", "test"],
                        ["mix", "test", "--seed", "123"], ["mix", "compile"]):
            self.assertTrue(m.is_heavy_command(command), command)
        for command in (["mix", "test", "test/new_you/local_config_test.exs:10"],
                        ["mix", "test", "test/new_you"], ["mix", "test", "--only", "focused"]):
            self.assertFalse(m.is_heavy_command(command), command)

    def test_uncertain_heavy_permit_cannot_be_reused_by_a_later_job(self):
        m = module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            owner = {"lease_id": "a" * 32, "generation": "b" * 32}
            with m.concurrency_gate(root, "heavy", 1, owner=owner, wait=0.01):
                pass
            with self.assertRaisesRegex(m.SlotError, "capacity"):
                with m.concurrency_gate(root, "heavy", 1, owner=owner, wait=0.01):
                    self.fail("uncertain heavy capacity was reassigned")

    def test_completed_heavy_permit_is_reusable(self):
        m = module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            owner = {"lease_id": "a" * 32, "generation": "b" * 32}
            for _ in range(2):
                with m.concurrency_gate(root, "heavy", 1, owner=owner, wait=0.01) as permit:
                    permit["complete"] = True

    def test_only_exact_owner_comment_authorizes_manifest(self):
        from unittest.mock import patch
        m = module()
        digest = "a" * 64
        reference = "https://github.com/Carpe-Diem-Media/devcore-project/pull/6#issuecomment-123"
        data = {"user": {"login": "JCSchoeman96"}, "html_url": reference,
                "issue_url": "https://api.github.com/repos/Carpe-Diem-Media/devcore-project/issues/6",
                "body": m.GitHubApproval.text(digest)}
        def api(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, json.dumps(data), "")
        with patch.object(m.subprocess, "run", api):
            self.assertEqual(m.GitHubApproval.verify(digest, reference)["author"], "JCSchoeman96")
            for key, value in (("user", {"login": "JC-Agents"}), ("body", m.GitHubApproval.text("b" * 64)),
                               ("html_url", reference + "x"), ("issue_url", "https://api.github.com/repos/other/repo/issues/6")):
                old = data[key]
                data[key] = value
                with self.assertRaises(m.SlotError):
                    m.GitHubApproval.verify(digest, reference)
                data[key] = old

    def test_redaction_spans_chunks(self):
        m = module()
        redactor = m.Redactor(["synthetic-secret"])
        output = redactor.feed(b"prefix synthetic-") + redactor.feed(b"secret suffix") + redactor.feed(b"", final=True)
        self.assertEqual(output, b"prefix [REDACTED] suffix")
