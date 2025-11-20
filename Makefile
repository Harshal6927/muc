.PHONY: lint

lint:
	@echo "Running linters... 🔄"
	pre-commit install
	pre-commit run -a
	@echo "Linters completed. ✅"
