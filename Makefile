.PHONY: install playground test

install:
	uv venv
	uv pip install -e . --system-certs

playground:
	uv run adk web app --host 127.0.0.1 --port 8080

run-ambient:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8080

test:
	uv run python test_expense_graph.py

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	uv run agents-cli eval grade --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
