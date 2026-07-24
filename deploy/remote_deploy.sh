#!/usr/bin/env bash
set -Eeuo pipefail

release_dir="${1:?release directory is required}"
stack_revision="${2:?stack revision is required}"
deploy_ref="${3:?deploy ref is required}"
current_link="/opt/truco/current"
engine_unit="truco-engine.service"
frontend_unit="truco-frontend.service"
switched=false
previous_target=""

fail() {
  echo "deploy preflight failed: $*" >&2
  exit 1
}

wait_for_url() {
  local url="$1"
  local method="${2:-GET}"
  local attempt
  for ((attempt = 1; attempt <= 30; attempt += 1)); do
    if [ "$method" = HEAD ]; then
      if curl --fail --silent --show-error --head "$url" >/dev/null; then
        return 0
      fi
    elif curl --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

rollback() {
  local exit_code=$?
  trap - ERR
  if [ "$switched" = true ] && [ -n "$previous_target" ] && [ -d "$previous_target" ]; then
    echo "New release failed; restoring $previous_target." >&2
    ln -sfn "$previous_target" "$current_link"
    sudo /bin/systemctl daemon-reload
    sudo /bin/systemctl restart "$engine_unit" "$frontend_unit" || true
  fi
  exit "$exit_code"
}
trap rollback ERR

[[ "$release_dir" =~ ^/opt/truco/releases/[0-9a-f]{40}-[0-9]+-[0-9]+$ ]] \
  || fail "release directory must be /opt/truco/releases/<sha>-<run>-<attempt>"
[[ "$stack_revision" =~ ^[0-9a-f]{40}$ ]] \
  || fail "stack revision must be a full Git SHA"
[ -d "$release_dir" ] || fail "release directory does not exist"
[ -f "$release_dir/RELEASE.json" ] || fail "RELEASE.json is missing"
[ -f "$release_dir/Cargo.lock" ] || fail "server Cargo.lock is missing"
[ -f "$release_dir/crates/truco-server/Cargo.toml" ] \
  || fail "truco-server source is missing"
[ -f "$release_dir/truco-frontend/pnpm-lock.yaml" ] \
  || fail "web pnpm lock is missing"
[ -f /etc/truco/truco.env ] || fail "/etc/truco/truco.env is missing"

for command in node pnpm sfw cargo curl python3 sudo; do
  command -v "$command" >/dev/null || fail "$command is required"
done

python3 - "$release_dir/RELEASE.json" "$stack_revision" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    release = json.load(source)
if release.get("format") != "baixada-truco-release/v1":
    raise SystemExit("unsupported RELEASE.json format")
if release.get("stack_revision") != sys.argv[2]:
    raise SystemExit("RELEASE.json does not match requested stack revision")
PY

node_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
[[ "$node_major" =~ ^[0-9]+$ ]] && [ "$node_major" -ge 24 ] \
  || fail "Node.js 24 or newer is required"

engine_definition="$(sudo /bin/systemctl cat "$engine_unit")"
frontend_definition="$(sudo /bin/systemctl cat "$frontend_unit")"
grep -Fq '/opt/truco/current/target/release/truco-server' \
  <<<"$engine_definition" \
  || fail "$engine_unit must use target/release/truco-server"
grep -Fq '/opt/truco/current/truco-frontend' <<<"$frontend_definition" \
  || fail "$frontend_unit must use the multirepo web path"

if [ -e "$current_link" ] && [ ! -L "$current_link" ]; then
  fail "$current_link exists but is not a symlink"
fi
if [ -L "$current_link" ]; then
  previous_target="$(readlink -f "$current_link")"
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export npm_config_prefix="$HOME/.local"
export NODE_ENV=production
export NEXT_PUBLIC_STUDY_LAB_LINKS=false
export NEXT_PUBLIC_STUDY_MANIFEST_URL="${STUDY_MANIFEST_URL:-https://storage.googleapis.com/truco-study-artifacts/releases/20260716-stealth-v1/manifest.json}"
export NEXT_PUBLIC_SHOW_DEV_CONTROLS=false

cd "$release_dir"
sfw pnpm --dir truco-frontend install --frozen-lockfile
sfw cargo fetch --locked
cargo build --release -p truco-server --locked
pnpm --dir truco-frontend build

printf '%s\n' "$stack_revision" > DEPLOYED_STACK_REVISION
printf '%s\n' "$deploy_ref" > DEPLOYED_REF

ln -sfn "$release_dir" "$current_link"
switched=true

sudo /bin/systemctl daemon-reload
sudo /bin/systemctl restart "$engine_unit" "$frontend_unit"
wait_for_url http://127.0.0.1:4000/health
wait_for_url http://127.0.0.1:3002/en HEAD
sudo /bin/systemctl is-active "$engine_unit" >/dev/null
sudo /bin/systemctl is-active "$frontend_unit" >/dev/null

switched=false
trap - ERR
echo "Deployed ${deploy_ref} (${stack_revision}) from ${release_dir}."
