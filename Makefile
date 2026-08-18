SHELL := /bin/bash

# Package customization - users can override this
PACKAGE_NAME ?= boilerplate-datascience

.DEFAULT_GOAL = help

# help: help					- Display this makefile's help information
.PHONY: help
help:
	@grep "^# help\:" Makefile | grep -v grep | sed 's/\# help\: //' | sed 's/\# help\://'

# help: customize-package			- Customize package name
.PHONY: customize-package
customize-package:
	@echo "🔧 Customizing package name..."
	@echo "Current package name: $(PACKAGE_NAME)"
	@echo "Python module name: $(shell echo $(PACKAGE_NAME) | tr '-' '_')"
	@echo ""
	@echo "To customize, run:"
	@echo "  make customize-package PACKAGE_NAME=my-awesome-project"
	@echo ""
	@if [ "$(PACKAGE_NAME)" != "boilerplate-datascience" ]; then \
		echo "🔄 Updating package configuration..."; \
		sed -i.bak 's/name = "boilerplate-datascience"/name = "$(PACKAGE_NAME)"/' pyproject.toml; \
		sed -i.bak 's/packages = \["boilerplate_datascience"\]/packages = ["$(shell echo $(PACKAGE_NAME) | tr '-' '_')"]/' pyproject.toml; \
		mv src/boilerplate_datascience src/$(shell echo $(PACKAGE_NAME) | tr '-' '_'); \
		echo "✅ Package customized to: $(PACKAGE_NAME)"; \
		echo "✅ Python module: $(shell echo $(PACKAGE_NAME) | tr '-' '_')"; \
	else \
		echo "ℹ️  Using default package name. Run with PACKAGE_NAME to customize."; \
	fi

# help: setup					- Sync the development environment with uv
.PHONY: setup
setup: install-dev-requirements

.PHONY : install-dev-requirements install-requirements
install-dev-requirements:
	@uv sync --extra dev
	@echo "✅ Development dependencies synced"

install-requirements:
	@uv sync
	@echo "✅ Runtime dependencies synced"

# help: install_precommit			- Install pre-commit hooks
.PHONY: install_precommit
install_precommit:
	@uv run pre-commit install -t pre-commit
	@uv run pre-commit install -t pre-push

# help: format			- format code using the precommits
.PHONY: format
format:
	@uv run pre-commit run -a

# help: serve_docs_locally			- Serve docs locally on port 8001
.PHONY: serve_docs_locally
serve_docs_locally:
	@uv run --extra dev mkdocs serve --livereload -a localhost:8001

# help: build_docs			- Build documentation locally
.PHONY: build_docs
build_docs:
	@uv run --extra dev mkdocs build

# help: deploy_docs				- Deploy documentation to GitHub Pages
.PHONY: deploy_docs
deploy_docs:
	@$(MAKE) build_docs
	@uv run --extra dev mkdocs gh-deploy

# help: run_tests			- Run repository's tests
.PHONY: run_tests
run_tests:
	@uv run pytest tests/
