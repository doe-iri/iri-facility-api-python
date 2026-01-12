dev : .venv
	@source ./.venv/bin/activate && \
	    IRI_API_ADAPTER_facility=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_status=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_account=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_compute=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_filesystem=app.demo_adapter.DemoAdapter \
		IRI_API_ADAPTER_task=app.demo_adapter.DemoAdapter \
		API_URL_ROOT='http://127.0.0.1:8000' fastapi dev


.venv:
	@uv venv
	@uv pip install -e .


.PHONY: clean
clean:
	@rm -rf iri_sandbox
	@rm -rf .venv
