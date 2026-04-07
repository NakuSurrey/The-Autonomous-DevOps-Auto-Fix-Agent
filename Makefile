# ============================================
# Autonomous DevOps & Auto-Fix Agent
# One-click commands for setup, demo, and more
# ============================================

.PHONY: setup demo test export-sft evaluate clean help

# --- default target: show help ---
help:
	@echo ""
	@echo "  Autonomous DevOps & Auto-Fix Agent"
	@echo "  ====================================="
	@echo ""
	@echo "  make setup      Install dependencies + build Docker sandbox"
	@echo "  make demo       Run the agent (fixes bugs in the sandbox)"
	@echo "  make test       Run the sandbox test suite manually"
	@echo "  make export-sft Export SFT training data from agent logs"
	@echo "  make evaluate   Run the evaluation benchmark"
	@echo "  make clean      Stop containers and remove temp files"
	@echo ""
	@echo "  Prerequisites:"
	@echo "    - Python 3.10+"
	@echo "    - Docker (running)"
	@echo "    - Free Gemini API key in .env"
	@echo ""

# --- install dependencies and build the sandbox container ---
setup:
	@echo "[1/3] Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "[2/3] Building Docker sandbox..."
	docker-compose up -d --build
	@echo "[3/3] Checking .env file..."
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "  WARNING: .env file not found."; \
		echo "  Run: cp .env.example .env"; \
		echo "  Then add your Gemini API key."; \
		echo "  Get one free at: https://aistudio.google.com/app/apikey"; \
		echo ""; \
	else \
		echo "  .env file found. Ready to go."; \
	fi
	@echo ""
	@echo "  Setup complete. Run 'make demo' to start the agent."
	@echo ""

# --- run the agent on the sandbox ---
demo:
	@echo ""
	@echo "  Starting the Autonomous DevOps Agent..."
	@echo "  The agent will detect failing tests, diagnose bugs,"
	@echo "  write fixes, and verify them — all autonomously."
	@echo ""
	python -m agent.main

# --- run sandbox tests manually ---
test:
	@echo "Running tests inside the sandbox..."
	docker-compose exec sandbox pytest tests/ -v

# --- export SFT training data ---
export-sft:
	@echo "Exporting SFT dataset (Alpaca format)..."
	python -m agent.main --export-sft
	@echo ""
	@echo "Exporting SFT dataset (Chat format)..."
	python -m agent.main --export-sft --chat
	@echo ""
	@echo "Done. Check data/sft_dataset.jsonl and data/sft_dataset_chat.jsonl"

# --- run evaluation benchmark ---
evaluate:
	@echo "Running evaluation benchmark..."
	python -m agent.main --evaluate
	@echo ""
	@echo "Done. Check data/eval_report.json"

# --- clean up containers and temp files ---
clean:
	@echo "Stopping containers..."
	docker-compose down
	@echo "Removing Python cache..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
