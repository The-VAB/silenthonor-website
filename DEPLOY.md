# Silent Honor Foundation — Deployment & Restore Runbook

## Infrastructure (as-is)

| Piece | Where | Status (2026-07-13) |
|---|---|---|
| Backend API | Hostinger VPS `72.60.175.115` → `https://api.srv1077820.hstgr.cloud` — systemd `silenthonor`, uvicorn :8000, nginx reverse proxy, MongoDB | ✅ **UP** (`/api/health` → 200, v2.0.0) |
| Static frontend | intended `https://silenthonorfoundation.org` | ❌ **DOWN** — domain does not resolve (no DNS record) |
| Legacy site | `https://silenthonor.org` (WordPress, AWS `76.223.67.189`) | ✅ up (separate host) |

The frontend calls the API cross-site via cookies (`window.API_BASE` in `js/components.js`).

## Why the site was down (root causes)

1. **DNS** — `silenthonorfoundation.org` (and `www.`) have no A record, so the frontend is unreachable. *(Registrar/DNS action — see step 1.)*
2. **CORS** — the live API only allowed `silenthonor.org`, so even once the frontend resolves, every logged-in call from `silenthonorfoundation.org` was blocked. *(Fixed in this PR — env-driven CORS now allows both domains; requires an API redeploy.)*
3. **No frontend server config** — the repo only shipped an API nginx block; nothing served the static site. *(Fixed — `scripts/silenthonor-frontend.nginx.conf` added.)*
4. **Leaked admin credential** — a credentials file was committed to this public repo. *(Untracked + gitignored + startup no longer writes it in production. The affected admin password must be rotated — step 4.)*

## What this PR fixes (code — deploy to take effect)

- Env-driven CORS (`CORS_ORIGINS`) defaulting to both prod domains + www + localhost.
- `server.py` no longer hardcodes `/app`; frontend dir auto-detected → clean-URL routes work on the VPS.
- Missing-page returns a branded `404.html` (added) instead of a 500.
- Startup skips writing `test_credentials.md` when `ENVIRONMENT=production`.
- `docker-compose` local stack works (backend now reads `MONGODB_URI`/`MONGODB_DB`).
- `.env.example` documents every variable the code actually reads.

## Restore procedure

**1. DNS (registrar / Cloudflare) — required, only the owner can do this**
   - Decide the canonical domain: **`silenthonorfoundation.org`** (new) or reuse **`silenthonor.org`** (replaces WordPress).
   - Point it at the VPS: `A silenthonorfoundation.org → 72.60.175.115` and `A www → 72.60.175.115` (proxy off / DNS-only for cert issuance).

**2. Frontend hosting on the VPS**
   ```bash
   ssh root@72.60.175.115
   cd /var/www/silenthonor && git pull origin main
   cp scripts/silenthonor-frontend.nginx.conf /etc/nginx/sites-available/silenthonor-frontend
   ln -sf /etc/nginx/sites-available/silenthonor-frontend /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   certbot --nginx -d silenthonorfoundation.org -d www.silenthonorfoundation.org
   ```
   *(If `silenthonor.org` is the chosen domain, set that in the `server_name` and certbot instead, and update `CORS_ORIGINS`.)*

**3. Redeploy the API (picks up the CORS fix)**
   ```bash
   cd /var/www/silenthonor/backend && git pull origin main
   # ensure /var/www/silenthonor/backend/.env has ENVIRONMENT=production and, if desired,
   # CORS_ORIGINS=https://silenthonorfoundation.org,https://www.silenthonorfoundation.org
   pip install -r requirements.txt
   systemctl restart silenthonor
   ```
   or run `scripts/deploy.sh` from a machine with SSH access.

**4. Rotate the leaked admin credential — required**
   The seed admin password was exposed in the public repo history. Set a new strong
   `ADMIN_PASSWORD` in `.env` and `systemctl restart silenthonor` (startup resets the
   admin hash to the env value). Optionally purge the old file from git history
   (`git filter-repo`) — a force-push, so coordinate first.

## Verify (after steps 1–4)

```bash
curl -s https://api.srv1077820.hstgr.cloud/api/health           # {"status":"healthy",...}
curl -s -D- -o /dev/null -H "Origin: https://silenthonorfoundation.org" \
     https://api.srv1077820.hstgr.cloud/api/health | grep -i access-control-allow-origin
curl -s -o /dev/null -w "%{http_code}\n" https://silenthonorfoundation.org   # 200
```
Then in a browser: load the site, sign up / log in, confirm the dashboard loads and the
auth cookie is set (DevTools → Application → Cookies).

## Local development

```bash
cp backend/.env.example backend/.env   # fill values
docker compose up --build              # frontend :3000, backend :8000, mongo :27017
```
