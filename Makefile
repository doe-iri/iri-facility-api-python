dev : .venv
	@source ./.venv/bin/activate && fastapi dev


.venv:
	@uv venv
	@uv pip install -e .


.PHONY: clean
clean:
	@rm -rf .venv
