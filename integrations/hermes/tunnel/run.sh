#!/bin/sh
set -eu
: "${HERMES_TUNNEL_HOST:?HERMES_TUNNEL_HOST is required}"
: "${HERMES_TUNNEL_USER:?HERMES_TUNNEL_USER is required}"
: "${HERMES_TUNNEL_REMOTE_PORT:?HERMES_TUNNEL_REMOTE_PORT is required}"
: "${HERMES_TUNNEL_HOSTKEY_ALIAS:?HERMES_TUNNEL_HOSTKEY_ALIAS is required}"
case "$HERMES_TUNNEL_HOST" in *[!a-zA-Z0-9.-]*|'') echo 'Invalid tunnel host' >&2; exit 2;; esac
case "$HERMES_TUNNEL_USER" in *[!a-zA-Z0-9_-]*|'') echo 'Invalid tunnel user' >&2; exit 2;; esac
case "$HERMES_TUNNEL_HOSTKEY_ALIAS" in *[!a-zA-Z0-9.-]*|'') echo 'Invalid host key alias' >&2; exit 2;; esac
case "$HERMES_TUNNEL_REMOTE_PORT" in *[!0-9]*|'') echo 'Invalid tunnel port' >&2; exit 2;; esac
if [ "$HERMES_TUNNEL_REMOTE_PORT" -lt 1024 ] || [ "$HERMES_TUNNEL_REMOTE_PORT" -gt 65535 ]; then echo 'Invalid tunnel port' >&2; exit 2; fi
test -s /run/hermes-tunnel/id_ed25519
test -s /run/hermes-tunnel/known_hosts
umask 077
mkdir -p /tmp/hermes-tunnel
cp /run/hermes-tunnel/id_ed25519 /tmp/hermes-tunnel/id_ed25519
chmod 600 /tmp/hermes-tunnel/id_ed25519
while :; do
  ssh -F /dev/null -N -T -i /tmp/hermes-tunnel/id_ed25519 \
    -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -o StrictHostKeyChecking=yes -o "HostKeyAlias=${HERMES_TUNNEL_HOSTKEY_ALIAS}" -o UserKnownHostsFile=/run/hermes-tunnel/known_hosts \
    -R "127.0.0.1:${HERMES_TUNNEL_REMOTE_PORT}:api:8510" \
    "${HERMES_TUNNEL_USER}@${HERMES_TUNNEL_HOST}" || true
  sleep 15
done
