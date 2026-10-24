# Restaurant Studio prototype recovery

Status: source archive not yet recovered (2026-10-24). Do not rebuild or deploy until original archive is inspected.

## Original artifact

- Filename: `restaurant-demo-v0.1.zip`
- Historical generation: 2026-10-19, "PapaSmurf Restaurant Studio v0.1"
- Previously generated as a ChatGPT downloadable artifact; not available in current working session or file library search.
- Expected structure: browser-only prototype centered on `index.html`.
- Expected features: editable restaurant name, phone, address, hours, description; three themes (Rustic, Modern, Midnight); immediate preview; JSON settings download.
- Expected limitations: no server-side customer storage, no account system, no automated publishing.
- These are historical descriptions, **not** verified archive contents.

## Repository baseline

On 2026-10-24, `main` contained only `docs-gateway/` and `vps-backup/`; no restaurant source was present. Repository: `hkusp45c/GPT-Workspace`.

## Intended deployment (not performed)

- VPS Ubuntu 24.04, admin user, IP 107.174.121.8.
- Caddy already serves other sites; preserve existing configuration.
- Proposed demo hostname `demo.sparkinthedarkness.com`, static site under `/srv/restaurant-demo`.
- TLS via Caddy, Basic Auth, `noindex` and security headers.
- Docker Engine and Compose are available but unnecessary for initial static prototype.
- Existing encrypted OneDrive backup: `bash "$HOME/bin/vps-backup.sh"` via rclone `vpsbackup:`. Manual backup and isolated restore passed; no automated schedule.
- No direct SSH server access from ChatGPT; operator runs commands.

## Recovery gate

1. Locate or upload the original ZIP (previous-session sandbox artifact may no longer exist).
2. Inspect ZIP file list and hashes without extracting to the served directory.
3. Review HTML, JS, CSS, external dependencies, functionality and security properties.
4. Commit extracted, verified source to Git; exclude secrets.
5. Only then design a minimally invasive Caddy deployment, checking for hostname and path collisions first.

This document is a discovery record, not evidence of a running restaurant application.
