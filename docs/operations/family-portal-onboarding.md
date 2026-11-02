# Family Portal onboarding: FotoMind

Follows `C:\Development\FamilyPortal\docs\APP-ONBOARDING-GUIDE.md`. Steps marked
**(admin)** are done by the portal admin on the Pi or in Jenkins. FotoMind's code never
changes Caddy, other apps or the portal registry.

## Onboarding request (Step 5)

```markdown
### App onboarding request

- App id (kebab-case): fotomind
- Display name: FotoMind
- Short description: Local-first photo & video library with RAW development and AI
- Category: Media
- Icon (emoji) / colour: 📷 #8b5cf6
- GitHub repo: https://github.com/Gianpy99/FotoMind
- Container port: 8000
- Health path: /health
- Auth mode: portal
- Allowed groups (portal modes): family, admins
- Database: PostgreSQL (new DB needed: fotomind)
- Secrets needed (names only!): DATABASE_URL
- Persistent data volume: yes (fotomind-data, thumbnails/previews; plan ~20-50 GB)
- Desired subdomain: photos.borrellofamily.co.uk
```

Proposed host port: **8097**. On 2026-11-02, ports 8090–8096 were in use on the Pi and 8097
was free. Add it to the port registry in `HOSTING-STANDARD.md`.

## Admin checklist

1. ✅ **Database.** Done: roles, databases and `pg_hba` rules are listed in
   [deployment/raspberry-pi/README.md](../../deployment/raspberry-pi/README.md).
   > The Pi's PostgreSQL 15 listens on **5432** (`postgresql.conf`). The FamilyPortal docs
   > and template mention 1433, which does not match the running server.
2. ? **Jenkins credential + job.** Done (2026-11-02; build #1 deployed). Run
   [jenkins-setup.sh](../../deployment/raspberry-pi/jenkins-setup.sh) on the Pi. It creates
   the `fotomind-database-url` credential from the secrets file on the Pi and the `fotomind`
   pipeline job (polls `main`). From then on, **every push to `main` deploys to production.**
3. ? **DNS (admin).** Done. Wix A record `photos` → `89.35.197.23`.
4. ? **Caddy (admin).** Done (FamilyPortal `b9f131e`). Add to `reverse-proxy/Caddyfile`, then run `.\deploy.ps1 -SetupCaddy`:

   ```caddyfile
   photos.borrellofamily.co.uk {
   	import app_portal 8097
   }
   ```

5. ? **Portal registry (admin).** Done (repo and live copy). Add this entry to `public/config/services.json`, both in the
   repo and in the live copy on the Pi:

   ```json
   {
     "id": "fotomind",
     "name": "FotoMind",
     "description": "Libreria foto e video con sviluppo RAW e AI, locale e privata.",
     "url": "https://photos.borrellofamily.co.uk/",
     "location": "pi",
     "category": "Media",
     "port": 8097,
     "icon": "📷",
     "color": "#8b5cf6",
     "healthCheck": true,
     "healthUrl": "https://photos.borrellofamily.co.uk/health",
     "status": "running"
   }
   ```

   > **Do not run `register-app.ps1` as-is for FotoMind.** It adds a path route
   > `handle_path /fotomind/* { reverse_proxy localhost:8097 }` **without authentication**,
   > which would bypass the portal login, and it sets a `/fotomind/` URL. The SPA expects to
   > be served at `/` on its own subdomain. If you use the script anyway, pass `-SkipDeploy`,
   > then remove the `handle_path /fotomind/*` block and fix `url`/`healthUrl` before you
   > publish.

## Verification

```bash
curl -fsS http://127.0.0.1:8097/health                      # on the Pi: {"status":"ok",...}
curl -s -o /dev/null -w '%{http_code}\n' https://photos.borrellofamily.co.uk/api/v1/me   # 401
```

Then log in through the browser. The header should show the portal user.
