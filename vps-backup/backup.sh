#!/usr/bin/env bash
# Run as admin, not root. Uses sudo only for protected local reads.
set -Eeuo pipefail
umask 077
if (( EUID == 0 )); then
  echo "Run as admin without sudo; the script requests sudo when needed." >&2
  exit 1
fi
sudo -v
command -v rclone >/dev/null
command -v flock >/dev/null
exec 9>"$HOME/.vps-backup.lock"
flock -n 9 || { echo "Another backup is running." >&2; exit 1; }
rclone listremotes | grep -Fx 'vpsbackup:' >/dev/null
config_file=$(rclone config file | tail -n 1)
test -f "$config_file"
container=docs-gateway-gateway-1
volume=docs-gateway_gateway-data
mountpoint=$(sudo docker volume inspect "$volume" --format '{{.Mountpoint}}')
test -n "$mountpoint"
running=$(sudo docker inspect "$container" --format '{{.State.Running}}')
sudo test -d "$mountpoint"
out=/var/backups/vps-backups
sudo install -d -m 0700 -o "$(id -u)" -g "$(id -g)" "$out"
stage=$(mktemp -d "$out/stage.XXXXXXXX")
restart_needed=0
cleanup() {
  rc=$?
  trap - EXIT
  if (( restart_needed )); then
    sudo docker start "$container" >/dev/null || rc=1
  fi
  # Leave artifacts for diagnosis/retry; they are protected by a 0700 parent.
  if (( rc != 0 )); then echo "Backup failed; protected working files: $stage" >&2; fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$running" == true ]]; then
  restart_needed=1
  sudo docker stop --time 30 "$container" >/dev/null
fi
# Copy every SQLite/WAL file together while its only application writer is stopped.
sudo tar --acls --xattrs --numeric-owner -cpf "$stage/gateway-data.tar" -C "$mountpoint" .
if (( restart_needed )); then
  sudo docker start "$container" >/dev/null
  restart_needed=0
fi
date -u +%FT%TZ > "$stage/created-utc.txt"
sudo docker inspect "$container" --format '{{.Image}}' > "$stage/gateway-image-id.txt"
sudo docker volume inspect "$volume" > "$stage/volume.json"
rclone version > "$stage/rclone-version.txt"
sudo docker version > "$stage/docker-version.txt"
sudo docker compose -f /opt/docs-gateway/compose.yaml -f /opt/docs-gateway/compose.override.yaml config --quiet
dpkg-query -W > "$stage/packages.txt"
paths=(srv etc/caddy opt/docs-gateway etc/systemd/system)
for optional in var/lib/caddy etc/docker etc/apt/sources.list.d etc/apt/keyrings; do
  if sudo test -e "/$optional"; then paths+=("$optional"); fi
done
# Includes rclone credentials INSIDE the archive; archive is encrypted on upload.
paths+=("${config_file#/}")
stamp=$(date -u +%Y%m%dT%H%M%SZ)
name="racknerd-d89778e-$stamp-$(basename "$stage").tar.gz"
archive="$out/$name"
sudo tar --acls --xattrs --numeric-owner -czpf "$archive" -C / "${paths[@]}" -C "$stage" .
sudo chown "$(id -u):$(id -g)" "$archive"
chmod 0600 "$archive"
(cd "$out"; sha256sum "$name" > "$name.sha256")
rclone copyto "$archive" "vpsbackup:snapshots/$name" --immutable
rclone copyto "$archive.sha256" "vpsbackup:snapshots/$name.sha256" --immutable
printf 'UPLOADED: vpsbackup:snapshots/%s\n' "$name"
printf 'LOCAL: %s\n' "$archive"
printf 'Next: download that snapshot, verify SHA-256, then test an isolated restore.\n'
# Remove only this completed staging directory. Retain the archive for comparison.
sudo rm -rf -- "$stage"
