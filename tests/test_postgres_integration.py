"""Opt-in integration checks against disposable PostgreSQL containers."""

import os
import secrets
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "devcore-project"
RUN_INTEGRATION = os.environ.get("DEVCORE_RUN_POSTGRES_INTEGRATION") == "1"


class IntegrationFixtureTests(unittest.TestCase):
    """Exercise fixture boundaries without Docker or workstation resources."""
    def test_readiness_uses_authenticated_tcp_instead_of_temporary_unix_server(self):
        from unittest.mock import Mock
        fixture = PostgresIntegrationTests()
        fixture.admin_password = "synthetic-admin-password"
        fixture.containers = []
        fixture._run = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, "container-id", ""),
            subprocess.CompletedProcess([], 0, "127.0.0.1:54321\n", ""),
            subprocess.CompletedProcess([], 0, "1\n", ""),
        ])
        self.assertEqual(fixture._start_container("ci-owned"), 54321)
        probe = fixture._run.call_args_list[-1]
        arguments = probe.args[0]
        self.assertIn("-h 127.0.0.1", " ".join(arguments))
        self.assertNotIn(fixture.admin_password, " ".join(arguments))
        self.assertEqual(probe.kwargs.get("input_text"), fixture.admin_password + "\n")

    def test_bootstrap_failure_reports_connection_and_container_state_without_secrets(self):
        from unittest.mock import Mock
        fixture = PostgresIntegrationTests()
        fixture.admin_password = "synthetic-admin-password"
        fixture.dev_password = "synthetic-dev-password"
        fixture.test_password = "synthetic-test-password"
        fixture.new_passwords = ["synthetic-new-password"]
        fixture._docker_psql = Mock(return_value=subprocess.CompletedProcess([], 2, "",
            "server closed connection " + " ".join([fixture.admin_password, fixture.dev_password,
                fixture.test_password, *fixture.new_passwords])))
        fixture._run = Mock(return_value=subprocess.CompletedProcess([], 0, "running|0|false", ""))
        with self.assertRaises(AssertionError) as failure:
            fixture._create_admin("ci-owned")
        message = str(failure.exception)
        self.assertIn("exit 2", message)
        self.assertIn("server closed connection", message)
        self.assertIn("running|0|false", message)
        for password in (fixture.admin_password, fixture.dev_password, fixture.test_password,
                         *fixture.new_passwords):
            self.assertNotIn(password, message)


@unittest.skipUnless(
    RUN_INTEGRATION,
    "set DEVCORE_RUN_POSTGRES_INTEGRATION=1 to run disposable PostgreSQL integration checks",
)
class PostgresIntegrationTests(unittest.TestCase):
    image = "postgres:18.6-alpine"

    def setUp(self):
        if not shutil.which("docker"):
            self.fail("Docker is required for the opt-in PostgreSQL integration check")
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-postgres-integration-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.central = self.home / ".config" / "dev-core"
        self.project = self.root / "project"
        self.home.mkdir()
        self.central.mkdir(parents=True, mode=0o700)
        self.project.mkdir()
        self.containers = []
        self.container_names = [
            f"devcore-it-{secrets.token_hex(8)}-dev",
            f"devcore-it-{secrets.token_hex(8)}-test",
        ]
        self.admin_password = secrets.token_urlsafe(32)
        self.dev_password = secrets.token_urlsafe(32)
        self.test_password = secrets.token_urlsafe(32)
        self.new_passwords = None
        self._write_project()
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q"],
            cwd=self.project,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            ports = [self._start_container(name) for name in self.container_names]
            self._write_global_config(*ports)
            for name in self.container_names:
                self._create_admin(name)
        except Exception:
            self._remove_containers()
            self.temp.cleanup()
            raise

    def tearDown(self):
        try:
            self._remove_containers()
        finally:
            if hasattr(self, "temp"):
                self.temp.cleanup()

    def _write_project(self):
        config = self.project / ".devcore"
        config.mkdir()
        (self.project / ".gitignore").write_text(
            ".env.dev\n.env.test\n.env.shared\n.env.local\n"
        )
        (config / "project.conf").write_text(
            "PROJECT_KEY=integration\n"
            "DEV_DB_ROLE=integration_dev\n"
            "DEV_DB_NAME=integration_dev\n"
            "TEST_DB_ROLE=integration_test\n"
            "TEST_DB_NAME=integration_test\n"
            "DEV_SECRET_KEY=INTEGRATION_DEV_DB_PASSWORD\n"
            "TEST_SECRET_KEY=INTEGRATION_TEST_DB_PASSWORD\n"
            "TEST_ROLE_CREATEDB=no\n"
            "USE_REDIS=no\n"
            "REDIS_PREFIX=integration\n"
            "RENDER_MAP=.devcore/render-map.tsv\n"
        )
        (config / "env.dev.template").write_text(
            "DEV_DATABASE_USERNAME={{DEV_DB_ROLE}}\n"
            "DEV_DATABASE_PASSWORD={{DEV_DB_PASSWORD}}\n"
            "DEV_DATABASE_HOST={{DEV_DB_HOST}}\n"
            "DEV_DATABASE_PORT={{DEV_DB_PORT}}\n"
            "DEV_DATABASE_NAME={{DEV_DB_NAME}}\n"
        )
        (config / "env.test.template").write_text(
            "TEST_DATABASE_USERNAME={{TEST_DB_ROLE}}\n"
            "TEST_DATABASE_PASSWORD={{TEST_DB_PASSWORD}}\n"
            "TEST_DATABASE_HOST={{TEST_DB_HOST}}\n"
            "TEST_DATABASE_PORT={{TEST_DB_PORT}}\n"
            "TEST_DATABASE_NAME={{TEST_DB_NAME}}\n"
        )
        (config / "env.shared.template").write_text(
            "SHARED_PROJECT_KEY={{PROJECT_KEY}}\n"
        )
        (config / "render-map.tsv").write_text(
            "dev\t.devcore/env.dev.template\t.env.dev\t\n"
            "test\t.devcore/env.test.template\t.env.test\t\n"
            "all\t.devcore/env.shared.template\t.env.shared\t\n"
        )

    def _write_global_config(self, dev_port, test_port):
        (self.central / "dev-core.conf").write_text(
            "PG_DEV_HOST=127.0.0.1\n"
            f"PG_DEV_PORT={dev_port}\n"
            "PG_TEST_HOST=127.0.0.1\n"
            f"PG_TEST_PORT={test_port}\n"
            "REDIS_DEV_HOST=127.0.0.1\n"
            "REDIS_DEV_PORT=56379\n"
            "REDIS_TEST_HOST=127.0.0.1\n"
            "REDIS_TEST_PORT=56380\n"
            f"PG_DEV_CONTAINER={self.container_names[0]}\n"
            f"PG_TEST_CONTAINER={self.container_names[1]}\n"
            "REDIS_DEV_CONTAINER=unused-dev\n"
            "REDIS_TEST_CONTAINER=unused-test\n"
            "PG_ADMIN_ROLE=devcore_admin\n"
        )
        (self.central / "dev-core.conf").chmod(0o600)

    def _start_container(self, name):
        result = self._run(
            [
                "docker", "run", "--detach", "--name", name,
                "--label", "devcore.integration=true",
                "--label", f"devcore.integration.id={name}",
                "--env", "POSTGRES_USER=postgres",
                "--env", "POSTGRES_PASSWORD",
                "--env", "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
                "--publish", "127.0.0.1::5432", self.image,
            ],
            env={"POSTGRES_PASSWORD": self.admin_password},
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, "could not start disposable PostgreSQL container")
        self.containers.append(name)
        port_result = self._run(["docker", "port", name, "5432/tcp"])
        self.assertEqual(port_result.returncode, 0, "could not read disposable PostgreSQL port")
        port = int(port_result.stdout.strip().rsplit(":", 1)[1])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            # The image starts a socket-only temporary server during initdb.
            # Only the final server accepts authenticated TCP connections.
            ready = self._run(["docker", "exec", "-i", name, "sh", "-c",
                'IFS= read -r PGPASSWORD || exit 1; export PGPASSWORD; '
                'exec psql -X -qAt -w -v ON_ERROR_STOP=1 -h 127.0.0.1 '
                '-U postgres -d postgres -c "SELECT 1"'],
                input_text=self.admin_password + "\n", check=False)
            if ready.returncode == 0:
                return port
            time.sleep(0.5)
        self.fail("disposable PostgreSQL container did not become ready")

    def _create_admin(self, container):
        result = self._docker_psql(
            container,
            "CREATE ROLE devcore_admin WITH LOGIN SUPERUSER;",
            check=False,
        )
        if result.returncode:
            state = self._run(["docker", "inspect", "-f",
                "{{.State.Status}}|{{.State.ExitCode}}|{{.State.OOMKilled}}", container], check=False)
            self.fail(self._redact(f"isolated DevCore admin bootstrap exit {result.returncode}; "
                      f"container state {state.stdout.strip()}; {result.stderr.strip()}"))

    def _redact(self, text):
        for password in (self.admin_password, self.dev_password, self.test_password,
                         *(getattr(self, "new_passwords", None) or [])):
            if password:
                text = text.replace(password, "[REDACTED]")
        return text

    def _docker_psql(self, container, sql, check=True):
        result = self._run(
            ["docker", "exec", "-i", container, "psql", "-X", "-qAt", "-v",
             "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-c", sql],
            check=check,
        )
        if check:
            self.assertEqual(result.returncode, 0,
                self._redact(f"CI-owned PostgreSQL SQL exit {result.returncode}: {result.stderr.strip()}"))
        return result

    def _run(self, args, *, env=None, timeout=30, check=True, input_text=None):
        child_env = os.environ.copy()
        child_env.update(env or {})
        return subprocess.run(
            args,
            cwd=self.project,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )

    def _tool(self, *args, expected=0):
        result = self._run(
            [str(TOOL), *args],
            env={
                "HOME": str(self.home),
                "DEVCORE_CONFIG_DIR": str(self.central),
                "DEVCORE_GLOBAL_CONF": str(self.central / "dev-core.conf"),
                "DEVCORE_SECRETS_FILE": str(self.central / "project-db.env"),
                "DEVCORE_PROJECT_CONF": ".devcore/project.conf",
            },
        )
        output = result.stdout + result.stderr
        secrets_to_check = [self.admin_password, self.dev_password, self.test_password]
        secrets_to_check.extend(getattr(self, "new_passwords", []) or [])
        for secret in secrets_to_check:
            self.assertNotIn(secret, output, "CLI output exposed a database credential")
        self.assertEqual(result.returncode, expected, "DevCore command returned an unexpected status")
        return result

    def _authenticate(self, container, role, password):
        address = self._run(
            [
                "docker", "inspect", "--format",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container,
            ]
        )
        self.assertEqual(address.returncode, 0, "could not inspect disposable PostgreSQL address")
        self.assertTrue(address.stdout.strip(), "disposable PostgreSQL container has no bridge address")
        return self._run(
            ["docker", "exec", "-i", container, "sh", "-c",
             'IFS= read -r PGPASSWORD || exit 1; export PGPASSWORD; exec psql -X -qAt -h "$2" -U "$1" -d "$1" -c "SELECT current_user"',
             "devcore-auth", role, address.stdout.strip()],
            input_text=password + "\n",
            check=False,
        )

    def test_activate_rotate_and_detect_database_and_render_drift(self):
        secrets_file = self.central / "project-db.env"
        secrets_file.write_text(
            f"INTEGRATION_DEV_DB_PASSWORD={self.dev_password}\n"
            f"INTEGRATION_TEST_DB_PASSWORD={self.test_password}\n"
        )
        secrets_file.chmod(0o600)

        self._tool("activate")
        self._assert_database_invariants(self.container_names[0], "integration_dev", "f")
        self._assert_database_invariants(self.container_names[1], "integration_test", "f")
        self._tool("doctor")

        self._tool("rotate")
        current_secrets = secrets_file.read_text().splitlines()
        self.new_passwords = [line.split("=", 1)[1] for line in current_secrets]
        for container, role, old_password, new_password in (
            (self.container_names[0], "integration_dev", self.dev_password, self.new_passwords[0]),
            (self.container_names[1], "integration_test", self.test_password, self.new_passwords[1]),
        ):
            old_auth = self._authenticate(container, role, old_password)
            self.assertNotEqual(
                old_auth.returncode,
                0,
                f"old credential still authenticated for {role}; changed={old_password != new_password}",
            )
            authenticated = self._authenticate(container, role, new_password)
            self.assertEqual(authenticated.returncode, 0, "rotated credential did not authenticate")

        self._tool("render")
        self._tool("doctor")

        self._docker_psql(
            self.container_names[1],
            "ALTER ROLE integration_test CREATEDB;",
        )
        self._tool("doctor", expected=1)
        self._docker_psql(
            self.container_names[1],
            "ALTER ROLE integration_test NOCREATEDB; ALTER DATABASE integration_test OWNER TO postgres;",
        )
        self._tool("doctor", expected=1)
        self._docker_psql(
            self.container_names[1],
            "ALTER DATABASE integration_test OWNER TO integration_test;",
        )
        self._tool("doctor")

        rendered = self.project / ".env.test"
        rendered.write_text(rendered.read_text().replace("TEST_DATABASE_NAME=integration_test", "TEST_DATABASE_NAME=wrong_db"))
        self._tool("doctor", expected=1)

    def test_doctor_detects_role_membership_drift_in_both_directions(self):
        secrets_file = self.central / "project-db.env"
        secrets_file.write_text(
            f"INTEGRATION_DEV_DB_PASSWORD={self.dev_password}\n"
            f"INTEGRATION_TEST_DB_PASSWORD={self.test_password}\n"
        )
        secrets_file.chmod(0o600)
        self._tool("activate")
        self._tool("doctor")

        container = self.container_names[0]
        self._docker_psql(container, "CREATE ROLE membership_drift;")
        try:
            for sql, revoke in (
                ("GRANT membership_drift TO integration_dev;", "REVOKE membership_drift FROM integration_dev;"),
                ("GRANT integration_dev TO membership_drift;", "REVOKE integration_dev FROM membership_drift;"),
            ):
                self._docker_psql(container, sql)
                self._tool("doctor", expected=1)
                self._docker_psql(container, revoke)
                self._tool("doctor")
        finally:
            self._docker_psql(
                container,
                "REVOKE membership_drift FROM integration_dev; "
                "REVOKE integration_dev FROM membership_drift; "
                "DROP ROLE IF EXISTS membership_drift;",
                check=False,
            )

    def test_managed_slot_databases_are_isolated_restricted_and_fresh_on_reuse(self):
        # Only CI-owned disposable containers reach this injected adapter. The CLI
        # still requires the exact approved workstation endpoint and owner receipt.
        from tests.test_slots import module, approve_for_test
        m = module()
        container = self.container_names[1]
        inspected = self._run(["docker", "inspect", "-f", "{{.Id}}", container])
        self.assertEqual(inspected.returncode, 0, "could not inspect CI-owned TEST container")
        container_id = inspected.stdout.strip()
        passwords = {}
        def password(row):
            value = secrets.token_hex(32)
            passwords[row["role"]] = value
            return value
        adapter = m.Postgres(m.newyou_contract(), password, endpoint=lambda: container_id)
        pool = m.Pool(self.root / "slot-pool", m.newyou_contract(), adapter,
                      port_available=lambda _: True, approval_check=approve_for_test)
        pool.enable(pool.manifest_digest(), "ci-owned-disposable-targets")
        # This legacy analogue exists only inside this test's labelled container.
        # Default PUBLIC CONNECT must block provisioning before any managed role.
        self._docker_psql(container, "CREATE ROLE new_you_test LOGIN NOCREATEDB;")
        self._docker_psql(container, "CREATE DATABASE new_you_test OWNER new_you_test;")
        with self.assertRaisesRegex(m.SlotError, "legacy TEST PUBLIC CONNECT"):
            pool.acquire(str(self.root))
        blocked = pool.status()[0]
        self.assertEqual(blocked["state"], "free")
        self.assertEqual(passwords, {})
        self.assertEqual(adapter.executor("SELECT EXISTS(SELECT FROM pg_roles WHERE rolname="
                         + m.sql_literal(blocked["role"]) + ");"), "f")
        # Simulate separately authorized hardening on the CI-owned analogue only.
        # Production code never changes an existing database's privileges.
        self._docker_psql(container, "REVOKE CONNECT ON DATABASE new_you_test FROM PUBLIC;")
        self.assertEqual(adapter.executor("SELECT has_database_privilege('new_you_test', "
                         "'new_you_test', 'CONNECT');"), "t")
        paths = [self.root / "worktree-a", self.root / "worktree-b"]
        for path in paths:
            path.mkdir()
        import concurrent.futures
        # Separate adapters avoid sharing the bound-connection attribute between jobs.
        def claim(path):
            own = m.Pool(pool.root, m.newyou_contract(),
                         m.Postgres(m.newyou_contract(), password, endpoint=lambda: container_id),
                         port_available=lambda _: True)
            return own.acquire(str(path))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            a, b = list(executor.map(claim, paths))
        self.assertNotEqual(a["database"], b["database"])
        def runtime(row, sql, database=None, target_container=None):
            result = self._run(
                ["docker", "exec", "-i", target_container or container_id, "sh", "-c",
                 'IFS= read -r PGPASSWORD || exit 1; export PGPASSWORD; exec psql -X -qAt -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$1" -d "$2" -c "$3"',
                 "slot-runtime", row["role"], database or row["database"], sql],
                input_text=passwords[row["role"]] + "\n", check=False)
            self.assertNotIn(passwords[row["role"]], result.stdout + result.stderr,
                             "runtime client exposed a synthetic credential")
            return result
        def value(row, sql):
            result = runtime(row, sql)
            self.assertEqual(result.returncode, 0, "slot runtime SQL failed")
            return result.stdout.strip()
        for row, marker in ((a, "synthetic-a"), (b, "synthetic-b")):
            self.assertEqual(value(row, "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user"), "f")
            self.assertEqual(value(row, f"CREATE TABLE isolation_probe(marker text); INSERT INTO isolation_probe VALUES ('{marker}'); SELECT marker FROM isolation_probe;"), marker)
        self.assertEqual(value(a, "SELECT marker FROM isolation_probe"), "synthetic-a")
        self.assertEqual(value(b, "SELECT marker FROM isolation_probe"), "synthetic-b")
        self.assertNotEqual(runtime(a, "SELECT 1", b["database"]).returncode, 0,
                            "slot A could connect to slot B")
        self.assertNotEqual(runtime(a, "SELECT 1", "new_you_test").returncode, 0,
                            "slot A could connect to protected legacy TEST")
        # DEV is a separate cluster, not another database on the TEST endpoint.
        # The managed LOGIN must not be created there or authenticate there.
        dev_inspected = self._run(["docker", "inspect", "-f", "{{.Id}}", self.container_names[0]])
        self.assertEqual(dev_inspected.returncode, 0, "could not inspect CI-owned DEV container")
        dev_id = dev_inspected.stdout.strip()
        self.assertNotEqual(dev_id, container_id)
        dev_role = self._docker_psql(dev_id, "SELECT EXISTS(SELECT FROM pg_roles WHERE rolname="
                                    + m.sql_literal(a["role"]) + ");")
        self.assertEqual(dev_role.stdout.strip(), "f")
        self.assertNotEqual(runtime(a, "SELECT 1", "postgres", target_container=dev_id).returncode, 0,
                            "TEST generation credentials authenticated on the DEV cluster")
        self.assertNotEqual(runtime(a, "CREATE DATABASE forbidden_extra_database").returncode, 0,
                            "runtime role unexpectedly had CREATEDB")
        # Migration DDL is allowed, but database ACLs remain administrative.
        # GRANT without a grant option can warn and return success, so inspect
        # the effective boundary rather than relying only on its exit status.
        original_acl = value(a, "SELECT datacl::text FROM pg_database WHERE datname=current_database()")
        for grantee in ("PUBLIC", b["role"]):
            runtime(a, f"GRANT CONNECT ON DATABASE {a['database']} TO {grantee}")
            self.assertEqual(value(a, "SELECT datacl::text FROM pg_database WHERE datname=current_database()"), original_acl,
                             "runtime role changed database ACL")
            self.assertNotEqual(runtime(b, "SELECT 1", a["database"]).returncode, 0,
                                "runtime role delegated access to its slot database")
        self.assertEqual(value(a, "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()"),
                         "devcore_admin")
        self.assertEqual(value(a, "SELECT has_database_privilege(current_user, current_database(), 'CONNECT WITH GRANT OPTION')"), "f")
        self.assertEqual(value(a, "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"), "f")
        self.assertEqual(value(a, "SELECT count(*) FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user)"), "0")
        self.assertNotEqual(runtime(a, "SET ROLE devcore_admin").returncode, 0,
                            "runtime role could assume administrative ownership")
        self.assertNotEqual(runtime(a, f"ALTER DATABASE {a['database']} OWNER TO {a['role']}").returncode, 0,
                            "runtime role could take database ownership")
        self.assertEqual(value(a, "BEGIN; CREATE TABLE migration_probe(id bigint PRIMARY KEY); "
                              "ALTER TABLE migration_probe ADD COLUMN marker text; "
                              "CREATE INDEX migration_probe_marker ON migration_probe(marker); "
                              "CREATE FUNCTION migration_identity(integer) RETURNS integer LANGUAGE SQL "
                              "AS 'SELECT $1'; CREATE TEMP TABLE temporary_probe(id integer); "
                              "COMMIT; SELECT migration_identity(7);"), "7")
        # Independent connections keep committed markers. Cleanup removes only A.
        pool.release(a["lease_id"], a["generation"], str(paths[0]))
        self.assertEqual(value(b, "SELECT marker FROM isolation_probe"), "synthetic-b")
        fresh = pool.acquire(str(paths[0]))
        self.assertEqual(fresh["slot"], a["slot"])
        self.assertNotEqual(fresh["database"], a["database"])
        self.assertEqual(value(fresh, "SELECT count(*) FROM pg_tables WHERE tablename='isolation_probe'"), "0")
        self.assertNotEqual(runtime(a, "SELECT 1").returncode, 0,
                            "old generation could still authenticate")
        pool.release(fresh["lease_id"], fresh["generation"], str(paths[0]))
        pool.release(b["lease_id"], b["generation"], str(paths[1]))

    def _assert_database_invariants(self, container, role, createdb):
        query = (
            "SELECT r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
            "r.rolreplication, r.rolbypassrls, pg_get_userbyid(d.datdba) "
            "FROM pg_roles r JOIN pg_database d ON d.datname = current_database() "
            f"WHERE r.rolname = '{role}'"
        )
        result = self._run(
            ["docker", "exec", container, "psql", "-X", "-qAt", "-F", "|",
             "-U", "postgres", "-d", role, "-c", query]
        )
        fields = result.stdout.strip().split("|")
        self.assertEqual(result.returncode, 0, "could not inspect disposable database role")
        self.assertEqual(fields, ["t", "f", createdb, "f", "f", "f", role])

    def _remove_containers(self):
        for name in getattr(self, "containers", []):
            try:
                subprocess.run(
                    ["docker", "rm", "--force", "--volumes", name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.containers = []


if __name__ == "__main__":
    unittest.main()
