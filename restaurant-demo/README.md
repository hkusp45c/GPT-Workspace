# PapaSmurf Restaurant Studio v0.1

A **static, private demonstration**. Zero back-end, no login database, no writable web endpoint, no third-party JS, no telemetry, no customer data storage. Browser-side fields generate a downloadable JSON settings file.

## Install on PapaSmurf

From Windows PowerShell (after extracting ZIP into C:\\dev\\restaurant-demo):

    scp -i "$HOME\.ssh\papasmurf" -r .\restaurant-demo admin@107.174.121.8:~/

From your SSH session as admin:

    sudo install -d -m 755 /srv/restaurant-demo
    sudo cp -a ~/restaurant-demo/index.html /srv/restaurant-demo/
    sudo chown -R root:root /srv/restaurant-demo
    sudo chmod 644 /srv/restaurant-demo/index.html

Cloudflare DNS: A record `demo` -> `107.174.121.8`; start DNS-only. Don't create a wildcard DNS record. Ensure there are no stale AAAA records.

Generate a password hash on the server:

    caddy hash-password

Enter a strong demo password; copy the resulting hash. **Never put the plaintext password in the Caddyfile.**

Append to `/etc/caddy/Caddyfile` (preserve existing site blocks):

    demo.sparkinthedarkness.com {
        basic_auth {
            demo REPLACE_WITH_FULL_HASH
        }
        root * /srv/restaurant-demo
        encode zstd gzip
        header {
            X-Robots-Tag "noindex, nofollow, noarchive"
            X-Content-Type-Options nosniff
            Referrer-Policy no-referrer
            X-Frame-Options DENY
        }
        file_server
    }

Then:

    sudo caddy validate --config /etc/caddy/Caddyfile
    sudo systemctl reload caddy
    curl -I https://demo.sparkinthedarkness.com

An unauthenticated curl should return **401 Unauthorized** (success). Browser authentication followed by HTTP 200 is expected. Caddy automatically requests and renews the HTTPS cert if DNS and reachability are correct.

## Security notes

- Basic auth is a **shared demo credential**, not multi-user authentication. Use strong, unique password and HTTPS.
- No public uploads, no user-supplied files or documents are processed server-side.
- `robots` noindex is not access control; authentication is.
- The public address, phone, menu and restaurant are **fictional placeholders**.
- Customer profiles are local browser values; download JSON to save. Reloading clears edits.
- On phones, the full editor stacks above the preview. Responsive layout is intentionally basic.
- This is a prototype of the **sales demo**, not the production provisioning system. The "Download site settings" button does not publish.

## Next iterations

1. More visually distinct templates and genuine owner-authorized photos.
2. Model menu uploads, PDF-to-HTML processing, source verification.
3. Per-prospect isolated previews from versioned JSON, expiry dates.
4. Safe, approved publishing workflow and offsite backups.
