# Include MCP-related targets
include mcp.mk

.PHONY: check-quality fix-quality commit clean compose-up compose-down tunnel-neo4j-http tunnel-neo4j-bolt run-pipeline run log-print deploy-agent-cloud-run export-requirements

AGENT_SERVICE_NAME ?= dod-deep-research-agent

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

tunnel-neo4j-http:
	@echo "Starting IAP tunnel to Neo4j HTTP port (7474)..."
	gcloud compute start-iap-tunnel neo4j-1 7474 --local-host-port=localhost:17474 --zone=us-west1-b

tunnel-neo4j-bolt:
	@echo "Starting IAP tunnel to Neo4j Bolt port (7687)..."
	gcloud compute start-iap-tunnel neo4j-1 7687 --local-host-port=localhost:17687 --zone=us-west1-b

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
	elif [ -n "$(LOG)" ]; then \
		case "$(LOG)" in \
			before_model) jq_filter=".payload.prompt" ;; \
			after_model) jq_filter=".payload.response" ;; \
			before_agent|after_agent) jq_filter="try (.payload.state | fromjson) catch .payload.state" ;; \
			before_tool) jq_filter=".payload.tool_args" ;; \
			after_tool) jq_filter=".payload.tool_response" ;; \
		esac; \
	fi; \
	if [ "$(LOG_UNESCAPE)" != "0" ] && ( [ -n "$(LOG_FIELD)" ] || [ "$(LOG)" = "after_model" ] ); then \
		jq_filter="$$jq_filter | gsub(\"\\\\\\\\n\"; \"\\n\")"; \
	fi; \
	jq_opts=""; \
	jq_color=""; \
	if [ "$(LOG_COLOR)" != "0" ]; then \
		jq_color="-C"; \
	fi; \
	if [ -n "$(LOG_RAW)" ] || [ -n "$(LOG_FIELD)" ]; then \
		jq_opts="-r"; \
	fi; \
	if [ -n "$$jq_color" ]; then \
		jq_opts="$$jq_opts $$jq_color"; \
	fi; \
	unescape_cmd="cat"; \
	if [ "$(LOG_UNESCAPE)" != "0" ]; then \
		unescape_cmd="python3 -c 'import sys;print(sys.stdin.read().replace(\"\\\\n\", \"\\n\"), end=\"\")'"; \
	fi; \
	if [ -n "$$log_file" ]; then \
		if [ ! -f "$$log_file" ]; then \
			echo "No log file found at $$log_file"; \
			exit 1; \
		fi; \
		sed -E 's/^\\[[^]]+\\] //' "$$log_file" | jq $$jq_opts "$$jq_filter" | eval "$$unescape_cmd"; \
		exit 0; \
	fi; \
	files=$$(ls "$$logs_dir"/* 2>/dev/null); \
	if [ -z "$$files" ]; then \
		echo "No logs found for agent: $(AGENT) in $$logs_dir"; \
		exit 1; \
	fi; \
	cat $$files | sed -E 's/^\\[[^]]+\\] //' | jq $$jq_opts "$$jq_filter" | eval "$$unescape_cmd"

export-requirements:
	@echo "Generating requirements.txt for ADK Cloud Run deploy..."
	uv export --no-dev -o dod_deep_research/requirements.txt

deploy-agent-cloud-run: export-requirements
	@test -n "$(GCP_PROJECT)" || (echo "GCP_PROJECT required (set in mcp.mk or override)"; exit 1)
	@test -n "$(GCP_REGION)" || (echo "GCP_REGION required (set in mcp.mk or override)"; exit 1)
	@test -n "$${PUBMED_MCP_URL}" || (echo "PUBMED_MCP_URL env var required"; exit 1)
	@test -n "$${CLINICAL_TRIALS_MCP_URL}" || (echo "CLINICAL_TRIALS_MCP_URL env var required"; exit 1)
	@test -n "$${EXA_MCP_URL}" || (echo "EXA_MCP_URL env var required"; exit 1)
	@envfile=$$(mktemp); \
	printf '%s\n' \
		"GOOGLE_CLOUD_PROJECT: $(GCP_PROJECT)" \
		"GOOGLE_CLOUD_LOCATION: $(GCP_REGION)" \
		"GOOGLE_GENAI_USE_VERTEXAI: \"$${GOOGLE_GENAI_USE_VERTEXAI:-True}\"" \
		"PUBMED_MCP_URL: \"$$PUBMED_MCP_URL\"" \
		"CLINICAL_TRIALS_MCP_URL: \"$$CLINICAL_TRIALS_MCP_URL\"" \
		"EXA_MCP_URL: \"$$EXA_MCP_URL\"" \
		> $$envfile; \
	uv run adk deploy cloud_run \
		--project=$(GCP_PROJECT) \
		--region=$(GCP_REGION) \
		--service_name=$(AGENT_SERVICE_NAME) \
		--with_ui \
		dod_deep_research \
		-- --allow-unauthenticated \
		--env-vars-file=$$envfile; \
	ec=$$?; rm -f $$envfile; exit $$ec
