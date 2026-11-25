#!/usr/bin/env bash
# Synthetic PostgreSQL 18.6 to 18.7 recovery rehearsal. No shared mounts or ports.
set -euo pipefail
umask 077
dir=$(mktemp -d)
name=devcore-rehearsal-${dir##*.}
old=postgres:18.6-alpine
new=devcore-postgres:18.7-vector0.8.7
started=$SECONDS
trap 'docker rm -fv "$name-source" "$name-upgrade" "$name-rollback" "$name-logical" >/dev/null 2>&1 || true; docker volume rm "$name-data" "$name-copy" >/dev/null 2>&1 || true; rm -rf "$dir"' EXIT
wait_db() {
  for _ in {1..60}; do
    if docker exec "$1" pg_isready -h 127.0.0.1 -U "$2" >/dev/null 2>&1; then return; fi
    sleep 0.5
  done
  return 1
}
sql() {
  docker exec "$1" psql -XqAt -v ON_ERROR_STOP=1 -U "$2" -d "$3" -c "$4"
}
df -B1 --output=avail "$dir" "$(docker info --format '{{.DockerRootDir}}')" 2>/dev/null || df -B1 --output=avail "$dir"
docker run -d --network none --name "$name-source" -e POSTGRES_HOST_AUTH_METHOD=trust -v "$name-data:/var/lib/postgresql" "$old" >/dev/null
wait_db "$name-source" postgres
sql "$name-source" postgres postgres 'CREATE ROLE project_owner LOGIN; CREATE ROLE project_reader; GRANT project_reader TO project_owner'
sql "$name-source" postgres postgres 'CREATE DATABASE project OWNER project_owner'
sql "$name-source" postgres project 'SET ROLE project_owner; CREATE TABLE fixture (value int); INSERT INTO fixture VALUES (42); GRANT SELECT ON fixture TO project_reader'
docker run --rm --network "container:$name-source" --entrypoint pg_dumpall "$new" -h 127.0.0.1 -U postgres --globals-only >"$dir/globals.sql"
docker run --rm --network "container:$name-source" --entrypoint pg_dump "$new" -h 127.0.0.1 -U postgres --create -Fc project >"$dir/project.dump"
docker stop --timeout 60 "$name-source" >/dev/null
test "$(docker inspect --format '{{.State.ExitCode}}' "$name-source")" = 0
docker run --rm --network none --entrypoint tar -v "$name-data:/snapshot:ro" "$old" -C /snapshot -cf - . >"$dir/physical.tar"
wc -c "$dir/globals.sql" "$dir/project.dump" "$dir/physical.tar"
docker run --rm -i --network none --entrypoint tar -v "$name-copy:/restore" "$old" -C /restore -xf - <"$dir/physical.tar"
docker run -d --network none --name "$name-upgrade" -v "$name-copy:/var/lib/postgresql" "$new" >/dev/null
wait_db "$name-upgrade" postgres
test "$(sql "$name-upgrade" postgres project 'SELECT value FROM fixture')" = 42
test "$(sql "$name-upgrade" postgres project "SELECT default_version FROM pg_available_extensions WHERE name='vector'")" = 0.8.7
docker run -d --network none --name "$name-rollback" -v "$name-data:/var/lib/postgresql" "$old" >/dev/null
wait_db "$name-rollback" postgres
test "$(sql "$name-rollback" postgres project 'SELECT value FROM fixture')" = 42
test "$(sql "$name-rollback" postgres project 'SHOW server_version')" = 18.6
printf 'Cold capture, upgraded clone and original-image rollback elapsed %ss\n' "$((SECONDS-started))"
docker run -d --network none --name "$name-logical" -e POSTGRES_USER=postgres -e POSTGRES_HOST_AUTH_METHOD=trust "$new" >/dev/null
wait_db "$name-logical" postgres
sed '/^CREATE ROLE postgres;$/d' "$dir/globals.sql" | docker exec -i "$name-logical" psql -Xq -v ON_ERROR_STOP=1 -U postgres -d postgres
docker exec -i "$name-logical" pg_restore --exit-on-error --create -U postgres -d postgres <"$dir/project.dump"
test "$(sql "$name-logical" postgres project "SELECT value, pg_has_role('project_owner','project_reader','MEMBER'), has_table_privilege('project_reader','fixture','SELECT') FROM fixture")" = '42|t|t'
printf 'Logical restore verified row, role membership and table ACL. Total %ss\n' "$((SECONDS-started))"
