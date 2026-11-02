# Database backup and restore (STO-005, STO-006)

The catalogue (ratings, tags, edit recipes, AI results, people) exists **only** in
PostgreSQL. Originals live on the PC disks and are backed up separately. Derived files
(thumbnails and previews) can be regenerated.

## Backup (on the Pi)

```bash
sudo mkdir -p /var/backups/fotomind && sudo chown postgres /var/backups/fotomind
sudo -u postgres pg_dump -Fc -d fotomind -f /var/backups/fotomind/fotomind_$(date +%F).dump
# keep 14 days
sudo find /var/backups/fotomind -name 'fotomind_*.dump' -mtime +14 -delete
```

Schedule this daily (root crontab or a systemd timer), and copy the dumps off the Pi (for
example to the PC backup disk). A backup isn't verified until it has been restored at
least once.

## Restore

```bash
docker stop fotomind
sudo -u postgres dropdb fotomind
sudo -u postgres createdb -O fotomind fotomind
sudo -u postgres pg_restore -d fotomind --no-owner --role=fotomind /var/backups/fotomind/fotomind_YYYY-MM-DD.dump
docker start fotomind          # migrations bring the schema up to the image's head
curl -fsS http://127.0.0.1:8097/health
```

To test a restore without touching production, restore into `fotomind_restore_test` and
point a local API at it.

## Derived data

The `fotomind-data` volume (thumbnails and previews) doesn't need a backup. The worker
regenerates it from the originals (EPIC 3).
