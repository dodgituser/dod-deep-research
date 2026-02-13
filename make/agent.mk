.PHONY: run-pipeline run log-print deploy-agent-cloud-run export-requirements create-outputs-bucket

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
	uv export --no-dev --no-hashes -o dod_deep_research/requirements.txt

deploy-agent-cloud-run: export-requirements
	@test -n "$(GCP_PROJECT)" || (echo "GCP_PROJECT required (set in Makefile or override)"; exit 1)
	@test -n "$(GCP_REGION)" || (echo "GCP_REGION required (set in Makefile or override)"; exit 1)
	@test -n "$(PUBMED_MCP_URL)" || (echo "PUBMED_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(CLINICAL_TRIALS_MCP_URL)" || (echo "CLINICAL_TRIALS_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(EXA_MCP_URL)" || (echo "EXA_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(NEO4J_MCP_URL)" || (echo "NEO4J_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@envfile=$$(mktemp); \
	printf '%s\n' \
		"GOOGLE_CLOUD_PROJECT: $(GCP_PROJECT)" \
		"GOOGLE_CLOUD_LOCATION: \"$(VERTEX_AI_LOCATION)\"" \
		"GOOGLE_GENAI_USE_VERTEXAI: \"$${GOOGLE_GENAI_USE_VERTEXAI:-True}\"" \
		"PUBMED_MCP_URL: \"$(PUBMED_MCP_URL)\"" \
		"CLINICAL_TRIALS_MCP_URL: \"$(CLINICAL_TRIALS_MCP_URL)\"" \
		"EXA_MCP_URL: \"$(EXA_MCP_URL)\"" \
		"NEO4J_MCP_URL: \"$(NEO4J_MCP_URL)\"" \
		> $$envfile; \
	uv run adk deploy cloud_run \
		--project=$(GCP_PROJECT) \
		--region=$(GCP_REGION) \
		--service_name=$(AGENT_SERVICE_NAME) \
		--with_ui \
		dod_deep_research \
		-- --allow-unauthenticated --no-invoker-iam-check \
		--env-vars-file=$$envfile; \
	ec=$$?; rm -f $$envfile dod_deep_research/requirements.txt; exit $$ec

create-outputs-bucket:
	@test -n "$(GCP_PROJECT)" || (echo "GCP_PROJECT required (set in Makefile or override)"; exit 1)
	@test -n "$(GCP_REGION)" || (echo "GCP_REGION required (set in Makefile or override)"; exit 1)
	gcloud storage buckets create gs://$(OUTPUTS_BUCKET) --project=$(GCP_PROJECT) --location=$(GCP_REGION) --uniform-bucket-level-access
