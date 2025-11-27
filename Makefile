.PHONY: lint release test test-fast coverage

lint:
	@echo "Running linters... 🔄"
	pre-commit install
	pre-commit run -a
	@echo "Linters completed. ✅"

test:
	@echo "Running tests... 🧪"
	uv run pytest tests/ -q
	@echo "Tests completed. ✅"

# test-fast:
# 	@echo "Running fast tests... ⚡"
# 	uv run pytest tests/ -q -m "not slow"
# 	@echo "Fast tests completed. ✅"

coverage:
	@echo "Running tests with coverage... 📊"
	uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/ ✅"

release:
	@python tools/prepare_release.py
	@uv sync
	@uv lock --upgrade
