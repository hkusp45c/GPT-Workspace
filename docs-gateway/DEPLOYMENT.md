# Deployment and recovery notes

These configuration files reproduce the commands used during the initial deployment.
Compare them with the VPS before treating them as an exact inventory of its present state.

## Host

Ubuntu 24.04 amd64, Docker Engine with Compose plugin, host-managed Caddy.
Project directory: /opt/docs-gateway. Published port: 127.0.0.1:8787.
No public Caddy route or MCP connection has been deployed for this gateway.
The docs hostname has DNS configured; DNS alone does not expose the gateway.

## Files and persistent state

- Dockerfile, compose.yaml, compose.override.yaml, .dockerignore, app/server.py.
- secrets/context7_api_key: deliberately absent from Git.
- Named Compose volume gateway-data at /data, normally docs-gateway_gateway-data.
  Confirm the real volume with docker inspect; do not assume its physical host path.
- /data/gateway.sqlite3 and its SQLite journal files contain the persistent ledger/cache.
  Use a SQLite online backup or stop the service before copying database files.
- Root-owned Docker operation: use sudo. Container UID/GID: 10001:10001.

## Recreate a host deployment

Create /opt/docs-gateway owned by the admin account and copy this directory there.
Create secrets/ with mode 0700 owned by admin. Enter the key using a hidden terminal
prompt; write it without a trailing newline, with file owner 10001:10001 and mode 0400.
Never put the key in shell history, Git, an image, or a pasted diagnostic.

Run from /opt/docs-gateway:

    sudo docker compose config --quiet
    sudo docker compose up -d --build
    curl --fail http://127.0.0.1:8787/health
    sudo docker compose exec -T gateway python /app/server.py status --sync

A newly created volume has no previous ledger or cache. Restore the backed-up
volume for continuity. Provider reconciliation alone does not recover grants or
conservative reservations for ambiguous requests.

## Park and resume

    sudo docker compose stop
    sudo docker compose start

Stop retains data and the existing container/image. Rebuild explicitly when code changes.
Never use docker compose down --volumes unless deliberately deleting persistent state.
The image uses the moving python:3.13-slim tag, so future rebuilds can use a different
base image. Record image IDs/digests during backups if exact reproduction is needed.

## Backups (next implementation stage)

Off-server backups must include website files under /srv, /etc/caddy, relevant
systemd configuration, the gateway deployment and secret, and consistent volume data.
Caddy service state/certificates may also be retained after locating its actual state
directory. Preserve owners and permissions. Encrypt before transferring secrets
off-host. Keep the recovery password somewhere independent of this VPS.
Do not publish the live Caddyfile: it can contain authentication hashes.

Recovery must restore to an isolated path and volume, use a different localhost port,
and check website content, Caddy configuration validity, and the gateway ledger/cache.
Do not query Context7 or reuse production authorization grants during restore testing.
