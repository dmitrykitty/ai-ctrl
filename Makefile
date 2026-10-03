.PHONY: bootstrap prepare test doctor claude-image claude-version claude-auth-status claude-login compose-config verify-auth-boundary verify-claude-state

bootstrap:
	./scripts/bootstrap.sh

# T01 preparation; local semantic models and dashboard assets come in T09.
prepare: bootstrap claude-image

test:
	./scripts/uv.sh run --frozen pytest

doctor:
	./scripts/uv.sh run --frozen aictrl doctor

claude-image:
	./scripts/claude-image.sh

claude-version:
	docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true --user 501:501 --entrypoint claude aictrl-claude:2.1.285-t01 --version

claude-auth-status:
	bash ./scripts/claude-auth-status.sh

claude-login:
	./scripts/claude-login.sh

compose-config:
	docker compose -f docker/compose.yaml --profile runtime config --quiet
	docker compose -f docker/compose.auth.yaml config --quiet

verify-auth-boundary:
	./scripts/verify-auth-boundary.sh

verify-claude-state:
	./scripts/verify-claude-state.sh
