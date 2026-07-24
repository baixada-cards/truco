# Production deployment contract

This directory contains the public, auditable mechanics for assembling and
activating a Baixada Truco production release. It deliberately contains no
hostnames, credentials, cloud resource names, live environment values, or
licensed files.

## Safety boundary

The `Production` GitHub Actions workflow is manual-only. Every dispatch runs
the compatibility checks; the `deploy` input defaults to false. The deploy job
also requires:

- the workflow revision to equal the current protected `main` revision;
- approval and secrets from the `production` GitHub environment;
- a passing `CI` run for that same revision;
- short-lived Google Workload Identity Federation credentials;
- a pinned SSH `known_hosts` entry; and
- a Droplet already prepared for Node 24 and the `truco-server` binary name.

The workflow never uploads a release artifact. Licensed runtime audio moves
directly from private Google Cloud Storage into the ephemeral runner and then
over SSH as part of the release tree.

## Release contents

`assemble_release.py` copies Git-tracked files from the exact server and web
checkouts selected by `stack.lock.json`. It separately verifies and copies the
five files described by the web repository's `private-audio.lock.json`.
Working-tree debris, Git metadata, dependencies, build outputs, test reports,
environment files, credential files, and symlinks are rejected or excluded.

The resulting layout is:

```text
release/
  Cargo.toml
  Cargo.lock
  crates/
  truco-frontend/
  deploy/remote_deploy.sh
  RELEASE.json
```

## Host activation

`remote_deploy.sh` fails before building unless the host already has:

- Node.js 24 or newer, pnpm, Socket Firewall, Rust/Cargo, curl, and systemd;
- `/etc/truco/truco.env`;
- `truco-engine.service` configured for
  `/opt/truco/current/target/release/truco-server`; and
- `truco-frontend.service` configured against
  `/opt/truco/current/truco-frontend`.

After frozen installs and locked builds, it atomically updates
`/opt/truco/current`, restarts both services, and checks the local server and
web endpoints. Any failure after the switch restores the previous symlink and
restarts the previous release.

Exact infrastructure setup, first migration, external smoke checks, and manual
rollback procedures are maintained in the private `baixada-ops` repository.
