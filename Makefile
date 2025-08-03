.PHONY: help install setup start stop test clean vectorize search

help: ## Show this help message
	@echo "Code Vectorizer - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

setup: ## Setup the project (environment + containers)
	@echo "Setting up Code Vectorizer..."
	@if [ ! -f .env ]; then \
		echo "Creating .env file from template..."; \
		cp env.example .env; \
		echo "Please edit .env file with your OpenAI API key"; \
	fi
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "✅ Setup complete! API available at http://localhost:8000"
	@echo "📖 API docs: http://localhost:8000/docs"

start: ## Start all services
	docker-compose up -d

stop: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

test: ## Test the API
	@echo "Testing API health..."
	@curl -f http://localhost:8000/api/health || echo "❌ API not responding"

clean: ## Clean up containers and data
	docker-compose down -v
	docker system prune -f

vectorize: ## Vectorize a repository via API (usage: make vectorize REPO_URL=<url> USERNAME=<user>)
	@if [ -z "$(REPO_URL)" ] || [ -z "$(USERNAME)" ]; then \
		echo "Usage: make vectorize REPO_URL=<repository-url> USERNAME=<username>"; \
		echo "Example: make vectorize REPO_URL=https://github.com/username/repo USERNAME=john_doe"; \
		exit 1; \
	fi
	curl -X POST "http://localhost:8000/api/vectorize" \
		-H "Content-Type: application/json" \
		-d '{"repo_url": "$(REPO_URL)", "username": "$(USERNAME)"}'

search: ## Search for code via API (usage: make search QUERY="your query" USERNAME=<user>)
	@if [ -z "$(QUERY)" ] || [ -z "$(USERNAME)" ]; then \
		echo "Usage: make search QUERY=\"your search query\" USERNAME=<username>"; \
		echo "Example: make search QUERY=\"function to parse JSON\" USERNAME=john_doe"; \
		exit 1; \
	fi
	curl -X POST "http://localhost:8000/api/search" \
		-H "Content-Type: application/json" \
		-d '{"query": "$(QUERY)", "username": "$(USERNAME)"}'

list-repos: ## List all vectorized repositories via API (usage: make list-repos USERNAME=<user>)
	@if [ -z "$(USERNAME)" ]; then \
		echo "Usage: make list-repos USERNAME=<username>"; \
		echo "Example: make list-repos USERNAME=john_doe"; \
		exit 1; \
	fi
	curl "http://localhost:8000/api/user/$(USERNAME)/repos"

delete: ## Delete a repository via API (usage: make delete REPO_NAME=<name> USERNAME=<user>)
	@if [ -z "$(REPO_NAME)" ] || [ -z "$(USERNAME)" ]; then \
		echo "Usage: make delete REPO_NAME=<repository-name> USERNAME=<username>"; \
		echo "Example: make delete REPO_NAME=my-repo USERNAME=john_doe"; \
		exit 1; \
	fi
	curl -X DELETE "http://localhost:8000/api/user/$(USERNAME)/repo/$(REPO_NAME)"

logs: ## Show all service logs
	docker-compose logs -f

pgadmin: ## Open pgAdmin in browser
	@echo "Opening pgAdmin at http://localhost:8080"
	@echo "Username: admin@vectorize.com"
	@echo "Password: admin123"
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:8080; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:8080; \
	else \
		echo "Please open http://localhost:8080 in your browser"; \
	fi

status: ## Show service status
	docker-compose ps

# Development commands (if you have Python installed)
dev-server: ## Start the FastAPI server in development mode (requires Python)
	uvicorn server:app --reload --host 0.0.0.0 --port 8000

test-api: ## Test the API with example client (requires Python)
	python client_example.py

docs: ## Open API documentation
	@echo "Opening API docs at http://localhost:8000/docs"
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:8000/docs; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:8000/docs; \
	else \
		echo "Please open http://localhost:8000/docs in your browser"; \
	fi

# Docker commands
build: ## Build the API Docker image
	docker-compose build

rebuild: ## Rebuild and restart all services
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d 