.PHONY: bootstrap prepare test test-fast doctor claude-image runtime-image gateway-image proxy-image claude-version claude-auth-status claude-login compose-config verify-auth-boundary verify-claude-state verify-runtime-boundary verify-gateway-boundary
.PHONY: codex-image codex-version codex-auth-status codex-login verify-codex-boundary
.PHONY: benchmark-gateway
.DEFAULT_GOAL := bootstrap

benchmark-gateway:
	./scripts/uv.sh run --frozen python scripts/benchmark-gateway.py --output .aictrl/benchmarks/latest.json

verify-codex-boundary:
	./scripts/uv.sh run --frozen python scripts/verify-codex-boundary.py

codex-image:
	bash ./scripts/codex-image.sh

codex-version:
	docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true --user 501:501 --entrypoint codex aictrl-codex:0.159.3-t05 --version

codex-auth-status:
	bash ./scripts/codex-auth-status.sh

codex-login:
	bash ./scripts/codex-login.sh

bootstrap:
	./scripts/bootstrap.sh

# Local semantic models and dashboard assets come in T09.
prepare: bootstrap runtime-image proxy-image gateway-image

test:
	./scripts/uv.sh run --frozen pytest

test-fast:
	./scripts/uv.sh run --frozen pytest tests/unit tests/security

doctor:
	./scripts/uv.sh run --frozen aictrl doctor

claude-image:
	./scripts/claude-image.sh

proxy-image:
	bash ./scripts/proxy-image.sh

runtime-image:
	bash ./scripts/runtime-image.sh

gateway-image:
	bash ./scripts/gateway-image.sh

claude-version:
	docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges:true --user 501:501 --entrypoint claude aictrl-claude:2.1.285-t02 --version

claude-auth-status:
	bash ./scripts/claude-auth-status.sh

claude-login:
	./scripts/claude-login.sh

compose-config:
	docker compose -f docker/compose.yaml --profile runtime config --quiet
	docker compose -f docker/compose.auth.yaml config --quiet
	docker compose -f docker/compose.codex-auth.yaml config --quiet

verify-auth-boundary:
	./scripts/verify-auth-boundary.sh

verify-claude-state:
	./scripts/verify-claude-state.sh

verify-runtime-boundary:
	./scripts/uv.sh run --frozen python scripts/verify-runtime-boundary.py

verify-gateway-boundary:
	./scripts/uv.sh run --frozen python scripts/verify-gateway-boundary.py
