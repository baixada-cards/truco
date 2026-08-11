# Agent Instructions

## Repository purpose

This repository owns Baixada Truco compatibility: exact public component
selection, nested-lock verification, source materialization, and the assembled
browser smoke test. It also owns the public, manually dispatched production
release contract. It is an integration root, not a source monorepo.

## Boundaries

- Component source changes belong in their owning repository.
- `stack.lock.json` uses full immutable Git revisions from public
  `baixada-cards` repositories only.
- Never copy component source into this repository or add Git submodules.
- Private operations, deployment identities, live inventories, credentials,
  licensed audio, and solver artifacts belong in `baixada-ops` or their
  approved private stores.
- Production deployments must be manual, target the exact protected `main`
  revision, and obtain private runtime assets through short-lived Google OIDC.
- Never add a long-lived cloud key, host inventory, secret value, licensed
  audio file, or uploaded release artifact to this repository.

## Workflow

- Update a component pin only after its upstream hosted checks pass.
- Run `make check` and `make verify` for every lock change.
- Run `make smoke` when the runtime stack changes; Chromium must already be
  installed locally.
- Run `make check` when the production workflow changes; the deployment
  contract test asserts the workflow stays manual, dry by default, and free of
  long-lived credentials.
- Use `sfw` for public-registry package fetches.
- Sign commits.

## Ports

The inherited web smoke owns ports 3002 and 4000. Never use port 3000 for an
agent-started process, and never stop a server you did not start.
