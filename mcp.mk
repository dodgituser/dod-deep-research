# MCP Server Configuration and Targets

MCP_DIR := mcp
PUBMED_MCP_SRC := ../pubmed-mcp-server/
CLINICAL_TRIALS_MCP_SRC := ../clinicaltrialsgov-mcp-server/
EXA_MCP_SRC := ../exa-mcp-server/
NEO4J_CYPHER_DIR := $(MCP_DIR)/mcp-neo4j/servers/mcp-neo4j-cypher

# GCP Cloud Run configuration
GCP_PROJECT ?= prod1-svc-27ah
GCP_REGION ?= us-west1
VERTEX_AI_LOCATION ?= global
ARTIFACT_REGISTRY_REPO ?= mcp-servers
PUBMED_SERVICE := pubmed-mcp
CLINICAL_TRIALS_SERVICE := clinicaltrials-mcp
EXA_SERVICE := exa-mcp
NEO4J_SERVICE := neo4j-cypher-mcp
CLOUD_RUN_VPC_CONNECTOR_NAME := serverless-connector
CLOUD_RUN_VPC_HOST_PROJECT := vpc-host-prod-cz879-bs784
CLOUD_RUN_VPC_SUBNET := connector-subnet
CLOUD_RUN_VPC_MACHINE_TYPE := e2-micro
CLOUD_RUN_VPC_MIN_INSTANCES := 2
CLOUD_RUN_VPC_MAX_INSTANCES := 10
CLOUD_RUN_VPC_EGRESS := private-ranges-only
CLOUD_RUN_VPC_NETWORK := vpc-prod-shared
# Connector lives in host project; Cloud Run references it by full path
CLOUD_RUN_VPC_CONNECTOR := projects/$(CLOUD_RUN_VPC_HOST_PROJECT)/locations/$(GCP_REGION)/connectors/$(CLOUD_RUN_VPC_CONNECTOR_NAME)
NEO4J_URI := bolt://10.10.0.30:7687
NEO4J_USERNAME := neo4j
NEO4J_DATABASE := neo4j
NEO4J_NAMESPACE :=
NEO4J_MCP_SERVER_ALLOWED_HOSTS := *
NEO4J_MCP_SERVER_ALLOW_ORIGINS :=
NEO4J_READ_TIMEOUT := 30

# Artifact Registry image paths
ARTIFACT_REGISTRY_BASE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(ARTIFACT_REGISTRY_REPO)
PUBMED_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(PUBMED_SERVICE):latest
CLINICAL_TRIALS_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(CLINICAL_TRIALS_SERVICE):latest
EXA_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(EXA_SERVICE):latest
NEO4J_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(NEO4J_SERVICE):latest

RSYNC_EXCLUDES := \
	--exclude '.git' \
	--exclude 'node_modules' \
	--exclude 'dist' \
	--exclude 'build' \
	--exclude '.next' \
	--exclude '.venv' \
	--exclude '__pycache__' \
	--exclude '.pytest_cache' \
	--exclude '.ruff_cache' \
	--exclude 'coverage' \
	--exclude 'logs'

.PHONY: sync-mcp build-mcp-pubmed build-mcp-clinical-trials build-mcp-exa build-mcp-neo4j build-mcp-all setup-artifact-registry setup-cloud-run-vpc-connector build-mcp-pubmed-cloud build-mcp-clinical-trials-cloud build-mcp-exa-cloud build-mcp-neo4j-cloud build-mcp-all-cloud push-mcp-pubmed-cloud push-mcp-clinical-trials-cloud push-mcp-exa-cloud push-mcp-neo4j-cloud push-mcp-all-cloud deploy-mcp-pubmed-cloud deploy-mcp-clinical-trials-cloud deploy-mcp-exa-cloud deploy-mcp-neo4j-cloud deploy-mcp-all-cloud

sync-mcp:
	@echo "Syncing MCP source snapshots into $(MCP_DIR)..."
	@mkdir -p $(MCP_DIR)/pubmed-mcp-server $(MCP_DIR)/clinicaltrialsgov-mcp-server $(MCP_DIR)/exa-mcp-server
	rsync -a --delete $(RSYNC_EXCLUDES) $(PUBMED_MCP_SRC) $(MCP_DIR)/pubmed-mcp-server/
	rsync -a --delete $(RSYNC_EXCLUDES) $(CLINICAL_TRIALS_MCP_SRC) $(MCP_DIR)/clinicaltrialsgov-mcp-server/
	rsync -a --delete $(RSYNC_EXCLUDES) $(EXA_MCP_SRC) $(MCP_DIR)/exa-mcp-server/

build-mcp-pubmed:
	@echo "Building pubmed-mcp:local..."
	docker build -t pubmed-mcp:local $(MCP_DIR)/pubmed-mcp-server

build-mcp-clinical-trials:
	@echo "Building clinicaltrialsgov-mcp:local..."
	docker build -t clinicaltrialsgov-mcp:local $(MCP_DIR)/clinicaltrialsgov-mcp-server

build-mcp-exa:
	@echo "Building exa-mcp:local..."
	docker build -t exa-mcp:local $(MCP_DIR)/exa-mcp-server

build-mcp-neo4j:
	@echo "Building neo4j-cypher-mcp:local..."
	docker build -t neo4j-cypher-mcp:local $(NEO4J_CYPHER_DIR)

build-mcp-all: build-mcp-pubmed build-mcp-clinical-trials build-mcp-exa build-mcp-neo4j
	@echo "Built all local MCP images."

# Cloud Run deployment targets
setup-artifact-registry:
	@echo "Setting up Artifact Registry repository..."
	@gcloud artifacts repositories create $(ARTIFACT_REGISTRY_REPO) \
		--repository-format=docker \
		--location=$(GCP_REGION) \
		--description="MCP servers container images" \
		2>/dev/null || echo "Repository $(ARTIFACT_REGISTRY_REPO) already exists or creation failed"

setup-cloud-run-vpc-connector:
	@echo "Creating Serverless VPC Access connector $(CLOUD_RUN_VPC_CONNECTOR_NAME) in host project $(CLOUD_RUN_VPC_HOST_PROJECT)..."
	@gcloud compute networks vpc-access connectors create $(CLOUD_RUN_VPC_CONNECTOR_NAME) \
		--region $(GCP_REGION) \
		--project $(CLOUD_RUN_VPC_HOST_PROJECT) \
		--subnet $(CLOUD_RUN_VPC_SUBNET) \
		--min-instances $(CLOUD_RUN_VPC_MIN_INSTANCES) \
		--max-instances $(CLOUD_RUN_VPC_MAX_INSTANCES) \
		--machine-type $(CLOUD_RUN_VPC_MACHINE_TYPE) \
		2>/dev/null || echo "Connector $(CLOUD_RUN_VPC_CONNECTOR_NAME) already exists or creation failed"
	@echo "Connector: $(CLOUD_RUN_VPC_CONNECTOR)"

# Build targets for Cloud Run
build-mcp-pubmed-cloud:
	@echo "Building pubmed-mcp for Cloud Run..."
	docker buildx build --platform linux/amd64 --load -t $(PUBMED_IMAGE) $(MCP_DIR)/pubmed-mcp-server

build-mcp-clinical-trials-cloud:
	@echo "Building clinicaltrials-mcp for Cloud Run..."
	docker buildx build --platform linux/amd64 --load -t $(CLINICAL_TRIALS_IMAGE) $(MCP_DIR)/clinicaltrialsgov-mcp-server

build-mcp-exa-cloud:
	@echo "Building exa-mcp for Cloud Run..."
	docker buildx build --platform linux/amd64 --load -t $(EXA_IMAGE) $(MCP_DIR)/exa-mcp-server

build-mcp-neo4j-cloud:
	@echo "Building neo4j-cypher-mcp for Cloud Run..."
	docker buildx build --platform linux/amd64 --load -t $(NEO4J_IMAGE) $(NEO4J_CYPHER_DIR)

build-mcp-all-cloud: build-mcp-pubmed-cloud build-mcp-clinical-trials-cloud build-mcp-exa-cloud build-mcp-neo4j-cloud
	@echo "Built all MCP images for Cloud Run."

# Push targets for Cloud Run
push-mcp-pubmed-cloud: build-mcp-pubmed-cloud
	@echo "Pushing pubmed-mcp to Artifact Registry..."
	docker push $(PUBMED_IMAGE)

push-mcp-clinical-trials-cloud: build-mcp-clinical-trials-cloud
	@echo "Pushing clinicaltrials-mcp to Artifact Registry..."
	docker push $(CLINICAL_TRIALS_IMAGE)

push-mcp-exa-cloud: build-mcp-exa-cloud
	@echo "Pushing exa-mcp to Artifact Registry..."
	docker push $(EXA_IMAGE)

push-mcp-neo4j-cloud: build-mcp-neo4j-cloud
	@echo "Pushing neo4j-cypher-mcp to Artifact Registry..."
	docker push $(NEO4J_IMAGE)

push-mcp-all-cloud: push-mcp-pubmed-cloud push-mcp-clinical-trials-cloud push-mcp-exa-cloud push-mcp-neo4j-cloud
	@echo "Pushed all MCP images to Artifact Registry."

# Deploy targets for Cloud Run
deploy-mcp-pubmed-cloud: push-mcp-pubmed-cloud
	@echo "Deploying pubmed-mcp to Cloud Run..."
	@gcloud run deploy $(PUBMED_SERVICE) \
		--image $(PUBMED_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--port 3017 \
		--set-env-vars "MCP_HTTP_PORT=3017,MCP_HTTP_HOST=0.0.0.0,MCP_TRANSPORT_TYPE=http,MCP_SESSION_MODE=stateless,MCP_LOG_LEVEL=info,MCP_FORCE_CONSOLE_LOGGING=true" \
		--memory 512Mi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 10 \
		--allow-unauthenticated

deploy-mcp-clinical-trials-cloud: push-mcp-clinical-trials-cloud
	@echo "Deploying clinicaltrials-mcp to Cloud Run..."
	@gcloud run deploy $(CLINICAL_TRIALS_SERVICE) \
		--image $(CLINICAL_TRIALS_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--port 3018 \
		--set-env-vars "MCP_HTTP_PORT=3018,MCP_HTTP_HOST=0.0.0.0,MCP_TRANSPORT_TYPE=http,MCP_SESSION_MODE=stateless,MCP_LOG_LEVEL=info,MCP_FORCE_CONSOLE_LOGGING=true" \
		--memory 512Mi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 10 \
		--allow-unauthenticated

deploy-mcp-exa-cloud: push-mcp-exa-cloud
	@if [ -z "$(EXA_API_KEY)" ]; then \
		echo "Error: EXA_API_KEY environment variable is required for Exa deployment"; \
		echo "Usage: make deploy-mcp-exa-cloud EXA_API_KEY=your-key"; \
		exit 1; \
	fi
	@echo "Deploying exa-mcp to Cloud Run..."
	@gcloud run deploy $(EXA_SERVICE) \
		--image $(EXA_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--port 3000 \
		--set-env-vars "EXA_API_KEY=$(EXA_API_KEY)" \
		--memory 512Mi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 10 \
		--allow-unauthenticated

deploy-mcp-neo4j-cloud: push-mcp-neo4j-cloud
	@echo "Deploying neo4j-cypher-mcp to Cloud Run..."
	@if [ -z "$$NEO4J_PASSWORD" ]; then \
		echo "Error: NEO4J_PASSWORD environment variable is required for Neo4j MCP deployment"; \
		echo "Usage: export NEO4J_PASSWORD=... && make deploy-mcp-neo4j-cloud"; \
		exit 1; \
	fi; \
	gcloud run deploy $(NEO4J_SERVICE) \
		--image $(NEO4J_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--port 8000 \
		--set-env-vars "NEO4J_URI=$(NEO4J_URI),NEO4J_USERNAME=$(NEO4J_USERNAME),NEO4J_PASSWORD=$$NEO4J_PASSWORD,NEO4J_DATABASE=$(NEO4J_DATABASE),NEO4J_NAMESPACE=$(NEO4J_NAMESPACE),NEO4J_TRANSPORT=http,NEO4J_MCP_SERVER_HOST=0.0.0.0,NEO4J_MCP_SERVER_PORT=8000,NEO4J_MCP_SERVER_PATH=/api/mcp/,NEO4J_MCP_SERVER_ALLOWED_HOSTS=$(NEO4J_MCP_SERVER_ALLOWED_HOSTS),NEO4J_MCP_SERVER_ALLOW_ORIGINS=$(NEO4J_MCP_SERVER_ALLOW_ORIGINS),NEO4J_READ_TIMEOUT=$(NEO4J_READ_TIMEOUT)" \
		--memory 512Mi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 10 \
		--allow-unauthenticated \
		--vpc-connector $(CLOUD_RUN_VPC_CONNECTOR) \
		--vpc-egress $(CLOUD_RUN_VPC_EGRESS)

deploy-mcp-all-cloud: deploy-mcp-pubmed-cloud deploy-mcp-clinical-trials-cloud deploy-mcp-exa-cloud deploy-mcp-neo4j-cloud
	@echo "Deployed all MCP servers to Cloud Run."
