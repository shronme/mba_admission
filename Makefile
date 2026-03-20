SHELL := /bin/bash

COMPOSE ?= docker compose
ROOT_DIR := $(CURDIR)
BACKEND_DIR := $(ROOT_DIR)/backend
WEB_DIR := $(ROOT_DIR)/apps/web

.PHONY: up down logs up-backend fe fe-prod build-fe lint-fe

## Bring up the entire system:
## 1) docker compose up (redis + postgres + API + worker)
## 2) start Next.js dev server (foreground)
up:
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Backend stack is up."
	@echo "Starting FE dev server (Next.js) on http://localhost:3000 ..."
	@if [ ! -d "$(WEB_DIR)/node_modules" ]; then \
		echo "Installing FE dependencies..."; \
		cd "$(WEB_DIR)" && npm install; \
	fi
	cd "$(WEB_DIR)" && npm run dev

## Only bring up backend services (no FE).
up-backend:
	$(COMPOSE) up -d --build

## Follow logs for backend services.
logs:
	$(COMPOSE) logs -f --tail=200

## Tear down backend services.
down:
	$(COMPOSE) down -v

## Start FE dev server only.
fe:
	@if [ ! -d "$(WEB_DIR)/node_modules" ]; then \
		echo "Installing FE dependencies..."; \
		cd "$(WEB_DIR)" && npm install; \
	fi
	cd "$(WEB_DIR)" && npm run dev

## Build FE for production (Next.js).
build-fe:
	cd "$(WEB_DIR)" && npm run build

## Lint FE.
lint-fe:
	cd "$(WEB_DIR)" && npm run lint

## Build and start FE in production mode (requires build-fe first).
fe-prod: build-fe
	cd "$(WEB_DIR)" && npm run start

