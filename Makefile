PYTHON      := python3.13
VENV        := .venv
BIN         := $(VENV)/bin
UV          := uv
PIP         := $(BIN)/pip
LOG_FILE    := runtime-logs.log
IRI_LOG_FILE ?= $(LOG_FILE)
LOG_ROTATION_DAYS := 5
IRI_LOG_ROTATION_DAYS ?= $(LOG_ROTATION_DAYS)

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
	[ -f local.env ] && source local.env || true && \
	IRI_API_ADAPTER_facility=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_status=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_account=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_compute=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_filesystem=app.demo_adapter.DemoAdapter \
	IRI_API_ADAPTER_task=app.demo_adapter.DemoAdapter \
	IRI_LOG_FILE="$${IRI_LOG_FILE:-$${LOG_FILE:-$(IRI_LOG_FILE)}}" \
	IRI_LOG_ROTATION_DAYS="$${IRI_LOG_ROTATION_DAYS:-$${LOG_ROTATION_DAYS:-$(IRI_LOG_ROTATION_DAYS)}}" \
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

globus: deps
	@source local.env && $(BIN)/python ./tools/globus.py

ARGS ?=

# call it via: make manage-globus ARGS=scopes-show
manage-globus: deps
	@source local.env && $(BIN)/python ./tools/manage_globus.py $(ARGS)
