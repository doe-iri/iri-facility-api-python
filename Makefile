dev : .venv
	@source ./.venv/bin/activate && \
		IRI_API_ADAPTER_status=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_account=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_compute=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_filesystem=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_task=app.demo_adapter.DemoAdapter \
		API_URL_ROOT='http://127.0.0.1:8000' fastapi dev


dev-s3df : .venv
	@source ./.venv/bin/activate && \
		IRI_API_ADAPTER_account=app.s3df.account_adapter.S3DFAccountAdapter \
		COACT_API_URL='https://coact-dev.slac.stanford.edu/graphql-service-dev' \
		IRI_SHOW_MISSING_ROUTES='true' \
		API_URL_ROOT='http://127.0.0.1:8000' fastapi dev


# --- Docker / GHCR targets ---
GHCR_USERNAME ?= ""
GHCR_IMAGE ?= ghcr.io/$(GHCR_USERNAME)/iri-s3df
IMAGE_TAG  ?= dev

# build for linux/amd64 (for now, since coact client only works on linux)
docker-build:
	docker build --platform linux/amd64 -t $(GHCR_IMAGE):$(IMAGE_TAG) .

docker-push: docker-build
	docker push $(GHCR_IMAGE):$(IMAGE_TAG)

# Test coact client locally inside the container (needs password)
docker-test-coact:
	@docker run --rm -it \
		-e COACT_SERVICE_PASSWORD \
		$(GHCR_IMAGE):$(IMAGE_TAG) \
		python -m app.s3df.clients.example


.venv:
	@uv venv
	@uv pip install -e .


.PHONY: clean
clean:
	@rm -rf iri_sandbox
	@rm -rf .venv
