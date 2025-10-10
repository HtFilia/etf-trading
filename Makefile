# ====== config ======
SHELL := /bin/bash
VENV := backend/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ACT := source $(VENV)/bin/activate

# Export keys from .env (values are read at runtime by python-dotenv anyway)
ifneq ("$(wildcard .env)","")
ENV_KEYS := $(shell sed -n 's/^\s*\([A-Za-z_][A-Za-z0-9_]*\)\s*=.*/\1/p' .env | xargs)
export $(ENV_KEYS)
endif

SESSION := amm

# ====== help ======
.PHONY: help
help:
	@echo "Usage:"
	@echo "  make env-init             					# create .env from .env.example if missing"
	@echo "  make venv                 					# create/upgrade virtualenv"
	@echo "  make install              					# env-init + venv"
	@echo "  make shell-venv           					# open an interactive shell with venv activated"
	@echo "  make fmt lint typecheck   					# code quality"
	@echo "  make test|test-unit|test-nr				# tests"
	@echo "  make up|down              					# start/stop ALL services in tmux (venv activated)"
	@echo "  make prod-up              					# start ALL services with prod flags"
	@echo "  make sim-pcf|sim-md|sim-fx|sim-pricing|ws  # start single service (venv activated)"
	@echo "  make clean clean-sockets full-clean		# clean everything"
	@echo "  make sockets								# status of sockets"

# ====== bootstrap ======
.PHONY: env-init
env-init:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: venv
venv:
	@test -d $(VENV) || (cd backend && python3 -m venv .venv)
	@$(PIP) -q install -U pip
	@$(PIP) -q install -r requirements.txt

.PHONY: install
install: env-init venv
	@echo "✅ Environment ready"

# ====== dev shell ======
.PHONY: shell-venv
shell-venv: venv
	@bash -lc '$(ACT); echo "Activated venv at $(VENV). Type exit to leave."; exec bash -i'

# ====== quality ======
.PHONY: fmt
fmt:
	@$(VENV)/bin/black -S -l 120 backend

.PHONY: lint
lint:
	@$(VENV)/bin/ruff check backend

.PHONY: typecheck
typecheck:
	@$(VENV)/bin/mypy backend || true

# ====== tests ======
.PHONY: test
test:
	@PYTHONPATH=. $(VENV)/bin/pytest -q

.PHONY: test-unit
test-unit:
	@PYTHONPATH=. $(VENV)/bin/pytest -q -m "unit"

.PHONY: test-nr
test-nr:
	@PYTHONPATH=. $(VENV)/bin/pytest -q -m "nr"

# ====== single service (foreground) — venv ACTIVATED ======
.PHONY: sim-pcf
sim-pcf: venv
	@bash -lc '$(ACT) && python backend/apps/simulation/pcf.py'

.PHONY: sim-md
sim-md: venv
	@bash -lc '$(ACT) && python backend/apps/simulation/market_data.py'

.PHONY: sim-fx
sim-fx: venv
	@bash -lc '$(ACT) && python backend/apps/simulation/fx.py'

.PHONY: sim-pricing
sim-pricing: venv
	@bash -lc '$(ACT) && python backend/apps/simulation/pricing.py'

.PHONY: ws
ws: venv
	@bash -lc '$(ACT) && python backend/apps/gateway_ws/main.py'

# ====== tmux orchestration (venv ACTIVATED in each pane) ======
.PHONY: up
up: install
	@echo "Starting dev grid (single window) in tmux session '$(SESSION)'..."
	@-tmux kill-session -t $(SESSION) 2>/dev/null || true
	# 1) create empty session + window
	@tmux new-session -d -s $(SESSION) -n stack "bash"
	# (tiny settle to avoid WSL races)
	@sleep 0.1
	# 2) make 5 panes: split -> [0|1], then split 0 & 1 vertically, then one more below pane 3
	@tmux split-window  -h -t $(SESSION):1
	@tmux split-window  -v -t $(SESSION):1.1
	@tmux split-window  -v -t $(SESSION):1.2
	@tmux split-window  -v -t $(SESSION):1.4
	# 3) arrange tiles and title each pane
	@tmux select-layout -t $(SESSION):1 tiled
	@tmux select-pane   -t $(SESSION):1.1 \; select-pane -T "pcf"
	@tmux select-pane   -t $(SESSION):1.2 \; select-pane -T "md"
	@tmux select-pane   -t $(SESSION):1.3 \; select-pane -T "fx"
	@tmux select-pane   -t $(SESSION):1.4 \; select-pane -T "pricing"
	@tmux select-pane   -t $(SESSION):1.5 \; select-pane -T "gateway_ws"
	# 4) run commands in each pane (venv ACTIVATED)
	@tmux send-keys -t $(SESSION):1.1 "bash -lc '$(ACT) && python backend/apps/simulation/pcf.py'" C-m
	@tmux send-keys -t $(SESSION):1.2 "bash -lc '$(ACT) && python backend/apps/simulation/market_data.py'"   C-m
	@tmux send-keys -t $(SESSION):1.3 "bash -lc '$(ACT) && python backend/apps/simulation/fx.py'"   C-m
	@tmux send-keys -t $(SESSION):1.4 "bash -lc '$(ACT) && python backend/apps/simulation/pricing.py'"  C-m
	@tmux send-keys -t $(SESSION):1.5 "bash -lc '$(ACT) && python backend/apps/gateway_ws/main.py'" C-m
	# 5) focus the gateway pane and attach
	@tmux select-pane -t $(SESSION):1.5
	@tmux attach -t $(SESSION)

.PHONY: down
down:
	@-tmux kill-session -t $(SESSION) 2>/dev/null || true
	@$(MAKE) clean-sockets

.PHONY: prod-up
prod-up: install
	@echo "Starting prod-ish grid (single window, JSON logs, dev_mode=off)..."
	@-tmux kill-session -t $(SESSION) 2>/dev/null || true
	@tmux new-session -d -s $(SESSION) -n stack "bash"
	@sleep 0.1
	@tmux split-window  -h -t $(SESSION):1
	@tmux split-window  -v -t $(SESSION):1.1
	@tmux split-window  -v -t $(SESSION):1.2
	@tmux split-window  -v -t $(SESSION):1.4
	@tmux select-layout -t $(SESSION):1 tiled
	@tmux select-pane   -t $(SESSION):1.1 \; select-pane -T "pcf_sim"
	@tmux select-pane   -t $(SESSION):1.2 \; select-pane -T "md_sim"
	@tmux select-pane   -t $(SESSION):1.3 \; select-pane -T "fx_sim"
	@tmux select-pane   -t $(SESSION):1.4 \; select-pane -T "pricing"
	@tmux select-pane   -t $(SESSION):1.5 \; select-pane -T "gateway_ws"
	@tmux send-keys -t $(SESSION):1.1 "bash -lc '$(ACT) && export LOG_FORMAT=json DEV_MODE=false && python backend/apps/pcf_sim/main.py'" C-m
	@tmux send-keys -t $(SESSION):1.2 "bash -lc '$(ACT) && export LOG_FORMAT=json DEV_MODE=false && python backend/apps/md_sim/main.py'"   C-m
	@tmux send-keys -t $(SESSION):1.3 "bash -lc '$(ACT) && export LOG_FORMAT=json DEV_MODE=false && python backend/apps/fx_sim/main.py'"   C-m
	@tmux send-keys -t $(SESSION):1.4 "bash -lc '$(ACT) && export LOG_FORMAT=json DEV_MODE=false && python backend/apps/pricing/main.py'"  C-m
	@tmux send-keys -t $(SESSION):1.5 "bash -lc '$(ACT) && export LOG_FORMAT=json DEV_MODE=false && python backend/apps/gateway_ws/main.py'" C-m
	@tmux select-pane -t $(SESSION):1.5
	@tmux attach -t $(SESSION)

# ====== utilities ======
.PHONY: sockets
sockets:
	@ls -l /tmp/etf-trading/*.sock 2>/dev/null || echo "No sockets in /tmp/etf-trading"

.PHONY: clean-sockets
clean-sockets:
	@rm -f /tmp/etf-trading/*.sock || true

.PHONY: clean
clean: clean-sockets
	@find backend -type d -name "__pycache__" -exec rm -rf {} + || true
	@rm -rf .pytest_cache || true
	@echo "🧹 Cleaned cache & sockets"

.PHONY: full-clean
full-clean: clean
	@rm -rf backend/.venv
	@rm -rf frontend/node_modules
	@rm -rf .mypy_cache
	@rm -rf .ruff_cache

