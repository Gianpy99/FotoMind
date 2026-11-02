# Raspberry Pi deployment

The Pi (Debian 12, aarch64) runs the `fotomind` container built and deployed by the
[Jenkinsfile](../../Jenkinsfile). Nothing here runs automatically. These are one-time
admin steps.

## 1. Databases (done 2026-11-02)

PostgreSQL 15 runs natively (systemd) on port **5432**. These objects exist; no other role
or database was changed:

| Role           | Database(s)                     | Allowed from (`pg_hba.conf`)                  |
| -------------- | ------------------------------- | --------------------------------------------- |
| `fotomind`     | `fotomind` (production)         | Docker `172.16.0.0/12` only                   |
| `fotomind_dev` | `fotomind_dev`, `fotomind_test` | Docker `172.16.0.0/12` + LAN `192.168.1.0/24` |

The passwords were generated on the Pi and are stored only there (`chmod 600`):

```
~/apps/fotomind/secrets/fotomind-database-url   # production URL -> Jenkins credential
~/apps/fotomind/secrets/{prod,dev}-db-password
~/apps/fotomind/.env                            # dev + test URLs (also copied to the PC's .env)
```

The original `pg_hba.conf` is backed up as `pg_hba.conf.bak-fotomind-<timestamp>` next to it.
To recreate everything by hand (it prompts for the passwords), use
[create-database.sql](create-database.sql) and [create-dev-databases.sql](create-dev-databases.sql).

## 2. Development space (`~/apps/fotomind`)

Used only by [scripts/pi-check.ps1](../../scripts/pi-check.ps1) from the PC:

```
~/apps/fotomind/.env      # from dev.env.example, chmod 600 (fotomind_dev credentials)
~/apps/fotomind/src/      # replaced on every pi-check run
```

Dev container `fotomind-dev` (image `fotomind:dev`) listens on `127.0.0.1:18097`, outside the
8090–8099 portal range and never published through Caddy.

## 3. Jenkins credential and job

```bash
scp deployment/raspberry-pi/jenkins-setup.* g99trading@192.168.1.129:/tmp/
ssh g99trading@192.168.1.129 "bash /tmp/jenkins-setup.sh && rm /tmp/jenkins-setup.*"
```

This creates the `fotomind-database-url` credential from the secrets file and the
`fotomind` job, which polls `main` every ~3 minutes. Jenkins restarts once while it runs.

## 4. Operations

```bash
docker logs -f fotomind                     # JSON logs on stdout
curl -fsS http://127.0.0.1:8097/health
docker volume inspect fotomind-data         # thumbnails / previews
```

- Rollback: Jenkins redeploys `fotomind:previous` automatically if the health check fails.
  To roll back manually, run the same `docker run` command with `fotomind:previous`.
- Migrations run at container start. A failing migration stops the app from starting, so the
  health check fails and Jenkins rolls back. Migrations must therefore be backward compatible with the previous image.
- Backups: [docs/operations/database-backup-restore.md](../../docs/operations/database-backup-restore.md).
