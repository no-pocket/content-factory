#!/bin/sh
set -eu
attempt=0
while [ ! -s /run/web-auth/token ]; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || { echo 'Private web API credential unavailable' >&2; exit 1; }
  sleep 1
done
WEB_TOKEN=$(cat /run/web-auth/token)
case "$WEB_TOKEN" in *[!a-f0-9]*|'') echo 'Invalid private web credential' >&2; exit 1;; esac
[ "${#WEB_TOKEN}" -eq 64 ] || exit 1
# Entry-point scripts run in subshells; substitute here rather than exporting to a sibling.
export WEB_TOKEN
envsubst '${WEB_TOKEN}' < /etc/nginx/content-factory.conf.template > /etc/nginx/conf.d/default.conf
