dev : .venv
	@source ./.venv/bin/activate && API_URL_ROOT='http://127.0.0.1:8000' fastapi dev


.venv:
	@uv venv
	@uv pip install -e .


.PHONY: clean
clean:
	@rm -rf .venv
