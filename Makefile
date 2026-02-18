PYTHON      := python3.14
VENV        := .venv
BIN         := $(VENV)/bin
UV          := uv
PIP         := $(BIN)/pip

STAMP_VENV  := $(VENV)/.created
STAMP_DEPS  := $(VENV)/.deps

.DEFAULT_GOAL := dev

$(STAMP_VENV):
	$(UV) venv $(VENV)
	touch $(STAMP_VENV)

.venv: $(STAMP_VENV)

$(STAMP_DEPS): $(STAMP_VENV) pyproject.toml
	$(UV) pip install --python $(BIN)/python -e .
	$(UV) pip install --python $(BIN)/python \
		ruff \
		pylint \
		bandit
	touch $(STAMP_DEPS)

deps: $(STAMP_DEPS)

dev: deps
	@source $(BIN)/activate && \
	IRI_API_ADAPTER_facility=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_status=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_account=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_compute=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_filesystem=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_task=app.demo_adapter.DemoAdapter \
	DEMO_QUEUE_UPDATE_SECS=2 \
	OPENTELEMETRY_ENABLED=true \
	API_URL_ROOT='http://localhost:8000' fastapi dev

.PHONY: clean
clean:
	rm -rf iri_sandbox
	rm -rf .venv

# Format and lint
format: deps
	$(BIN)/ruff format --line-length 200 .

ruff: deps
	$(BIN)/ruff check . --fix || true

pylint: deps
	find . -path ./$(VENV) -prune -o -type f -name "*.py" -print0 | while IFS= read -r -d '' f; do \
		echo "Pylint $$f"; \
		$(BIN)/pylint $$f --rcfile pylintrc || true; \
	done

# Security
audit: deps
	uv pip compile pyproject.toml -o requirements.txt
	uv pip sync requirements.txt
	uv pip install pip-audit
	$(BIN)/pip-audit || true
	rm -f requirements.txt

bandit: deps
	$(BIN)/bandit -r app || true

# Full validation bundle
lint: clean format ruff pylint audit bandit
