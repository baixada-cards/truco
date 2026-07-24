.PHONY: check materialize smoke smoke-installed verify

check:
	python3 scripts/check_stack.py
	python3 -m unittest discover -s tests

verify:
	python3 scripts/verify_public_stack.py

materialize:
	python3 scripts/materialize.py

smoke:
	python3 scripts/materialize.py --component web
	cd .components/web && sfw pnpm install --frozen-lockfile
	$(MAKE) smoke-installed

smoke-installed:
	cd .components/web && STUDY_LAB_MODE=public NEXT_PUBLIC_STUDY_LAB_LINKS=true pnpm exec playwright test tests/e2e/live-game.spec.ts --grep "starting a match syncs the url"
