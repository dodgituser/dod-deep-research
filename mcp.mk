# MCP Server Configuration and Targets

MCP_DIR := mcp
PUBMED_MCP_SRC := ../pubmed-mcp-server/
CLINICAL_TRIALS_MCP_SRC := ../clinicaltrialsgov-mcp-server/
EXA_MCP_SRC := ../exa-mcp-server/

# GCP Cloud Run configuration
GCP_PROJECT ?= prod1-svc-27ah
GCP_REGION ?= us-central1
ARTIFACT_REGISTRY_REPO ?= mcp-servers
PUBMED_SERVICE := pubmed-mcp
CLINICAL_TRIALS_SERVICE := clinicaltrials-mcp
EXA_SERVICE := exa-mcp

# Artifact Registry image paths
ARTIFACT_REGISTRY_BASE := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(ARTIFACT_REGISTRY_REPO)
PUBMED_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(PUBMED_SERVICE):latest
CLINICAL_TRIALS_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(CLINICAL_TRIALS_SERVICE):latest
EXA_IMAGE := $(ARTIFACT_REGISTRY_BASE)/$(EXA_SERVICE):latest

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

.PHONY: sync-mcp build-mcp-pubmed build-mcp-clinical-trials build-mcp-exa build-mcp-all setup-artifact-registry build-mcp-pubmed-cloud build-mcp-clinical-trials-cloud build-mcp-exa-cloud build-mcp-all-cloud push-mcp-pubmed-cloud push-mcp-clinical-trials-cloud push-mcp-exa-cloud push-mcp-all-cloud deploy-mcp-pubmed-cloud deploy-mcp-clinical-trials-cloud deploy-mcp-exa-cloud deploy-mcp-all-cloud

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

build-mcp-all: build-mcp-pubmed build-mcp-clinical-trials build-mcp-exa
	@echo "Built all local MCP images."

# Cloud Run deployment targets
setup-artifact-registry:
	@echo "Setting up Artifact Registry repository..."
	@gcloud artifacts repositories create $(ARTIFACT_REGISTRY_REPO) \
		--repository-format=docker \
		--location=$(GCP_REGION) \
		--description="MCP servers container images" \
		2>/dev/null || echo "Repository $(ARTIFACT_REGISTRY_REPO) already exists or creation failed"

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

build-mcp-all-cloud: build-mcp-pubmed-cloud build-mcp-clinical-trials-cloud build-mcp-exa-cloud
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

push-mcp-all-cloud: push-mcp-pubmed-cloud push-mcp-clinical-trials-cloud push-mcp-exa-cloud
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

deploy-mcp-all-cloud: deploy-mcp-pubmed-cloud deploy-mcp-clinical-trials-cloud deploy-mcp-exa-cloud
	@echo "Deployed all MCP servers to Cloud Run."
