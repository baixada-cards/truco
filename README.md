# Truco · Baixada

The compatibility and integration root for
[Baixada Truco](https://baixada.cards).

This repository deliberately contains no component source. `stack.lock.json`
selects one immutable, publicly fetchable revision of every contract,
implementation, research, service, design, and product repository that forms a
compatible Truco system.

| Component | Responsibility |
|---|---|
| [`truco-spec`](https://github.com/baixada-cards/truco-spec) | Rules, schemas, and executable fixtures |
| [`truco-engine`](https://github.com/baixada-cards/truco-engine) | Authoritative gameplay implementation |
| [`truco-solver`](https://github.com/baixada-cards/truco-solver) | CFR research and the policy-format contract |
| [`truco-bots`](https://github.com/baixada-cards/truco-bots) | Runtime bot implementations |
| [`truco-server`](https://github.com/baixada-cards/truco-server) | HTTP and hosted-session service |
| [`design-system`](https://github.com/baixada-cards/design-system) | Shared Baixada tokens and marks |
| [`truco-web`](https://github.com/baixada-cards/truco-web) | Browser product and BFF |

## Verify the stack

The offline gate checks manifest shape, immutable public origins, full Git
revisions, and full-SHA GitHub Actions:

```sh
make check
```

The public compatibility gate fetches the nested lock files from the exact
revisions and proves all nine dependency edges agree:

```sh
make verify
```

To obtain disposable component checkouts:

```sh
python3 scripts/materialize.py
```

They land under ignored `.components/` in dependency order. They are detached
at exact revisions and remain independent Git repositories.

## Assembled smoke test

The smallest real integration test materializes `truco-web`; its frozen
dependency graph builds the exact public design system and its Playwright
server launcher materializes the exact public server. A browser then creates a
real match through the BFF and checks that the match URL survives reload:

```sh
python3 scripts/materialize.py --component web
sfw pnpm --dir .components/web install --frozen-lockfile
pnpm --dir .components/web exec playwright install chromium
make smoke-installed
```

`make smoke` combines materialization, dependency installation through Socket
Firewall, and the final command when Chromium is already available.

## Updating compatibility

1. Merge and verify the component change in its owning repository.
2. Update the relevant full revision in `stack.lock.json`.
3. Run `make check`, `make verify`, and `make smoke`.
4. Merge this repository's protected pull request.

Never point the stack at `main`, a tag without its resolved commit, a sibling
checkout, or an unpublished/private source. Deployment identities, live
inventories, licensed source assets, and production secrets belong in the
private `baixada-ops` repository.
