# Agent Instructions

## Repository purpose

This repository owns Baixada Truco compatibility: exact public component
selection, nested-lock verification, source materialization, and the assembled
browser smoke test. It is an integration root, not a source monorepo.

## Boundaries

- Component source changes belong in their owning repository.
- `stack.lock.json` uses full immutable Git revisions from public
  `baixada-cards` repositories only.
- Never copy component source into this repository or add Git submodules.
- Private operations, deployment identities, live inventories, credentials,
  licensed audio, and solver artifacts belong in `baixada-ops` or their
  approved private stores.

## Workflow

- Update a component pin only after its upstream hosted checks pass.
- Run `make check` and `make verify` for every lock change.
- Run `make smoke` when the runtime stack changes; Chromium must already be
  installed locally.
- Use `sfw` for public-registry package fetches.
- Sign commits.

## Ports

The inherited web smoke owns ports 3002 and 4000. Never use port 3000 for an
agent-started process, and never stop a server you did not start.
