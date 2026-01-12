.PHONY: check-quality fix-quality commit clean compose-up compose-down run-pipeline run

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
	@echo "Starting docker compose services, building from scratch and starting in detached mode..."
	docker compose -f docker-compose.yml build --no-cache
	docker compose -f docker-compose.yml up -d

compose-down:
	@echo "Stopping docker compose services..."
	docker compose -f docker-compose.yml down

run-pipeline:
	@if [ -z "$(INDICATION)" ] || [ -z "$(DRUG_NAME)" ]; then \
		echo "Usage: make run-pipeline INDICATION='...' DRUG_NAME='...' [DRUG_FORM='...'] [DRUG_GENERIC_NAME='...']"; \
		exit 1; \
	fi
	@cmd="uv run dod-deep-research --indication \"$(INDICATION)\" --drug-name \"$(DRUG_NAME)\""; \
	if [ -n "$(DRUG_FORM)" ]; then cmd="$$cmd --drug-form \"$(DRUG_FORM)\""; fi; \
	if [ -n "$(DRUG_GENERIC_NAME)" ]; then cmd="$$cmd --drug-generic-name \"$(DRUG_GENERIC_NAME)\""; fi; \
	echo "$$cmd"; \
	eval $$cmd

run:
	@if [ -z "$(INDICATION)" ] || [ -z "$(DRUG_NAME)" ]; then \
		echo "Usage: make run INDICATION='...' DRUG_NAME='...' [DRUG_FORM='...'] [DRUG_GENERIC_NAME='...']"; \
		exit 1; \
	fi
	@mkdir -p outputs
	@docker compose -f docker-compose.yml --profile pipeline build --no-cache; \
	cmd="docker compose -f docker-compose.yml --profile pipeline run --rm -v \"$(PWD)/outputs:/app/dod_deep_research/outputs\" pipeline --indication \"$(INDICATION)\" --drug-name \"$(DRUG_NAME)\""; \
	if [ -n "$(DRUG_FORM)" ]; then cmd="$$cmd --drug-form \"$(DRUG_FORM)\""; fi; \
	if [ -n "$(DRUG_GENERIC_NAME)" ]; then cmd="$$cmd --drug-generic-name \"$(DRUG_GENERIC_NAME)\""; fi; \
	echo "$$cmd"; \
	eval $$cmd
