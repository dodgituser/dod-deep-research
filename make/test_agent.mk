.PHONY: export-test-agent-requirements deploy-test-agent-cloud-run

TEST_AGENT_SERVICE_NAME ?= dod-deep-research-test-agent

export-test-agent-requirements:
	@echo "Generating requirements.txt for ADK Cloud Run test-agent deploy..."
	uv export --no-dev --no-hashes -o tests/agents/requirements.txt

deploy-test-agent-cloud-run: export-test-agent-requirements
	@test -n "$(GCP_PROJECT)" || (echo "GCP_PROJECT required (set in Makefile or override)"; exit 1)
	@test -n "$(GCP_REGION)" || (echo "GCP_REGION required (set in Makefile or override)"; exit 1)
	@test -n "$(PUBMED_MCP_URL)" || (echo "PUBMED_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(CLINICAL_TRIALS_MCP_URL)" || (echo "CLINICAL_TRIALS_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(EXA_MCP_URL)" || (echo "EXA_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(NEO4J_MCP_URL)" || (echo "NEO4J_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@test -n "$(OLS_MCP_URL)" || (echo "OLS_MCP_URL required (set in make/mcp.mk or override)"; exit 1)
	@envfile=$$(mktemp); \
	printf '%s\n' \
		"GOOGLE_CLOUD_PROJECT: $(GCP_PROJECT)" \
		"GOOGLE_CLOUD_LOCATION: \"$(VERTEX_AI_LOCATION)\"" \
		"GOOGLE_GENAI_USE_VERTEXAI: \"$${GOOGLE_GENAI_USE_VERTEXAI:-True}\"" \
		"PUBMED_MCP_URL: \"$(PUBMED_MCP_URL)\"" \
		"CLINICAL_TRIALS_MCP_URL: \"$(CLINICAL_TRIALS_MCP_URL)\"" \
		"EXA_MCP_URL: \"$(EXA_MCP_URL)\"" \
		"NEO4J_MCP_URL: \"$(NEO4J_MCP_URL)\"" \
		"OLS_MCP_URL: \"$(OLS_MCP_URL)\"" \
		> $$envfile; \
	uv run adk deploy cloud_run \
		--project=$(GCP_PROJECT) \
		--region=$(GCP_REGION) \
		--service_name=$(TEST_AGENT_SERVICE_NAME) \
		--with_ui \
		tests/agents \
		-- --allow-unauthenticated --no-invoker-iam-check \
		--env-vars-file=$$envfile; \
	ec=$$?; rm -f $$envfile tests/agents/requirements.txt; exit $$ec
