#!/bin/bash
# =============================================================================
# jenkins-setup.sh - Jenkins credentials "fotomind-database-url" and "fotomind-worker-token"
# + job "fotomind". Run ON THE PI from the folder containing this script and
# jenkins-setup.groovy:
#   bash jenkins-setup.sh
# Reads ~/apps/fotomind/secrets/fotomind-database-url (created with the database) and
# ~/apps/fotomind/secrets/worker-token (generated here if missing), copies them into Jenkins
# for the init script (which deletes them), restarts Jenkins and waits. Safe to re-run.
# Does not start a build: the job polls main, so the first push to main deploys.
# =============================================================================
set -euo pipefail

J=ci_cd_validation_jenkins_1
JH=/var/jenkins_home
DIR="$(cd "$(dirname "$0")" && pwd)"
SECRETS=~/apps/fotomind/secrets
SECRET=$SECRETS/fotomind-database-url
TOKEN=$SECRETS/worker-token

docker ps --filter "name=$J" --format '{{.Names}}' | grep -q "$J" \
  || { echo "ERROR: container $J is not running"; exit 1; }
[ -s "$SECRET" ] || { echo "ERROR: $SECRET missing (create the database first)"; exit 1; }

if [ ! -s "$TOKEN" ]; then
  (umask 077 && openssl rand -hex 24 > "$TOKEN")
  echo "==> Generated worker token in $TOKEN (copy it to FOTOMIND_WORKER_TOKEN on the PC)"
fi

docker exec "$J" sh -c "mkdir -p $JH/init.groovy.d"
for pair in "$SECRET:fotomind_database_url" "$TOKEN:fotomind_worker_token"; do
  src=${pair%%:*}; dst=$JH/${pair##*:}
  docker cp "$src" "$J:$dst"
  docker exec -u 0 "$J" sh -c "chown 1000:1000 $dst && chmod 600 $dst"
done
docker cp "$DIR/jenkins-setup.groovy" "$J:$JH/init.groovy.d/fotomind-setup.groovy"

echo "==> Restarting Jenkins to run the init script..."
docker restart "$J" >/dev/null
for i in $(seq 1 60); do
  if docker exec "$J" sh -c "test -d $JH/jobs/fotomind && test ! -f $JH/init.groovy.d/fotomind-setup.groovy" 2>/dev/null; then
    echo "    Job 'fotomind' ready."
    break
  fi
  sleep 3
done
docker logs --since 5m "$J" 2>&1 | grep '\[fotomind-setup\]' || true
echo "Job: https://jenkins.borrellofamily.co.uk/job/fotomind/"
