# Entry point for all build/deploy targets.

# Global project configuration (non-MCP specific)
GCP_PROJECT ?= prod1-svc-27ah
GCP_REGION ?= us-west1
VERTEX_AI_LOCATION ?= global
AGENT_SERVICE_NAME ?= dod-deep-research-agent
OUTPUTS_BUCKET ?= dod-deep-research-outputs

.PHONY: check-quality fix-quality commit clean compose-up compose-down tunnel-neo4j-http tunnel-neo4j-bolt

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

include make/mcp.mk
include make/agent.mk
