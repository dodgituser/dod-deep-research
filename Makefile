.PHONY: check-quality fix-quality commit clean compose-up compose-down

check-quality:
	@echo "Checking formatting and linting with ruff..."
	@ruff check .
	@ruff format --check .

fix-quality:
	@echo "Auto-formatting and linting with ruff..."
	@ruff check --fix .
	@ruff format .

commit: fix-quality
	@echo "Committing changes..."
	git add .
	@aic -t conventional
	git push

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -r {} + 2>/dev/null || true
	@echo "Clean complete."

compose-up:
	@echo "Starting docker compose services..."
	docker compose -f docker-compose.yml up -d --build

compose-down:
	@echo "Stopping docker compose services..."
	docker compose -f docker-compose.yml down
