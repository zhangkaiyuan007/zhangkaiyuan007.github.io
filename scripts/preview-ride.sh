#!/usr/bin/env bash
# One-command preview of the disposable riding prototype.
set -euo pipefail
cd "$(dirname "$0")/.."
ride_hugo="${RIDE_HUGO:-hugo}"
if ! command -v "$ride_hugo" >/dev/null && [[ -x /tmp/kaiyuan-hugo/hugo ]]; then
  ride_hugo=/tmp/kaiyuan-hugo/hugo
fi
export GOMODCACHE="${GOMODCACHE:-/tmp/kaiyuan-go-mod}"
export GOPATH="${GOPATH:-/tmp/kaiyuan-go}"
exec "$ride_hugo" server --bind 127.0.0.1 --port "${RIDE_PORT:-1313}" --cacheDir /tmp/kaiyuan-hugo-cache
