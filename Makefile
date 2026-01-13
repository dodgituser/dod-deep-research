.PHONY: check-quality fix-quality commit clean compose-up compose-down run-pipeline run log-print

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

log-print:
	@if [ -z "$(AGENT)" ]; then \
		echo "Usage: make log-print AGENT='planner_agent' [LOG='before_tool' | LOG_FILE='planner_agent_callback_before_tool.jsonl']"; \
		exit 1; \
	fi
	@logs_dir="outputs/agent_logs/$(AGENT)"; \
	if [ ! -d "$$logs_dir" ]; then \
		echo "No logs directory found at $$logs_dir. Run the pipeline to generate logs."; \
		exit 1; \
	fi; \
	log_file=""; \
	if [ -n "$(LOG_FILE)" ]; then \
		log_file="$$logs_dir/$(LOG_FILE)"; \
	elif [ -n "$(LOG)" ]; then \
		log_suffix=$$(echo "$(LOG)" | tr ' ' '_' ); \
		log_file="$$logs_dir/$(AGENT)_callback_$${log_suffix}.jsonl"; \
	fi; \
	jq_filter="."; \
	if [ -n "$(LOG_FIELD)" ]; then \
		jq_filter=".payload.$(LOG_FIELD)"; \
	elif [ "$(LOG)" = "after_model" ]; then \
		jq_filter=".payload.response"; \
	fi; \
	if [ "$(LOG_UNESCAPE)" != "0" ] && ( [ -n "$(LOG_FIELD)" ] || [ "$(LOG)" = "after_model" ] ); then \
		jq_filter="$$jq_filter | gsub(\"\\\\\\\\n\"; \"\\n\")"; \
	fi; \
	jq_opts=""; \
	if [ -n "$(LOG_RAW)" ] || [ "$(LOG)" = "after_model" ] || [ -n "$(LOG_FIELD)" ]; then \
		jq_opts="-r"; \
	fi; \
	post_cmd="cat"; \
	if [ "$(LOG_UNESCAPE)" != "0" ]; then \
		post_cmd="awk 'BEGIN{RS=\"\"; ORS=\"\"} {gsub(/\\\\\\\\n/,\"\\n\"); print}'"; \
	fi; \
	if [ -n "$$log_file" ]; then \
		if [ ! -f "$$log_file" ]; then \
			echo "No log file found at $$log_file"; \
			exit 1; \
		fi; \
		sed -E 's/^\\[[^]]+\\] //' "$$log_file" | jq $$jq_opts "$$jq_filter" | $$post_cmd; \
		exit 0; \
	fi; \
	files=$$(ls "$$logs_dir"/* 2>/dev/null); \
	if [ -z "$$files" ]; then \
		echo "No logs found for agent: $(AGENT) in $$logs_dir"; \
		exit 1; \
	fi; \
	cat $$files | sed -E 's/^\\[[^]]+\\] //' | jq $$jq_opts "$$jq_filter" | $$post_cmd
