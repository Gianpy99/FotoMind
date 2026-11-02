#!/bin/bash
# =============================================================================
# jenkins-setup.sh - Jenkins credential "fotomind-database-url" + job "fotomind".
# Run ON THE PI from the folder containing this script and jenkins-setup.groovy:
#   bash jenkins-setup.sh
# Reads ~/apps/fotomind/secrets/fotomind-database-url (created with the database), copies
# it into Jenkins for the init script (which deletes it), restarts Jenkins and waits.
# Does not start a build: the job polls main, so the first push to main deploys.
# =============================================================================
set -euo pipefail

J=ci_cd_validation_jenkins_1
JH=/var/jenkins_home
DIR="$(cd "$(dirname "$0")" && pwd)"
SECRET=~/apps/fotomind/secrets/fotomind-database-url

docker ps --filter "name=$J" --format '{{.Names}}' | grep -q "$J" \
  || { echo "ERROR: container $J is not running"; exit 1; }
[ -s "$SECRET" ] || { echo "ERROR: $SECRET missing (create the database first)"; exit 1; }

docker exec "$J" sh -c "mkdir -p $JH/init.groovy.d"
docker cp "$SECRET" "$J:$JH/fotomind_database_url"
docker exec -u 0 "$J" sh -c "chown 1000:1000 $JH/fotomind_database_url && chmod 600 $JH/fotomind_database_url"
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
