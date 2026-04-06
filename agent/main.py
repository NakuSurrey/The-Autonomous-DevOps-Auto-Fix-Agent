"""
main.py — Entry Point for the Autonomous DevOps & Auto-Fix Agent

WHAT THIS FILE DOES:
    This is the file you run to start the agent.
    Command: python -m agent.main

WHY IT EXISTS:
    Every program needs an entry point — a single place where
    execution begins. This file validates the config, prints
    a startup banner, and kicks off the ReAct loop.

WHERE IT SITS IN THE CODEBASE:
    agent/main.py
    ├── Calls: agent/config.py (validate_config)
    ├── Calls: agent/react_loop.py (run_react_loop)
    ├── Calls: agent/sft_exporter.py (--export-sft flag)
    ├── Calls: agent/evaluator.py (--evaluate flag)
    └── This is the TOP of the call chain — nothing calls this file.
        You run it directly from the terminal.

HOW TO RUN:
    From the project root directory:
        python -m agent.main                  ← run the agent normally
        python -m agent.main --export-sft     ← export SFT dataset from logs
        python -m agent.main --evaluate       ← full evaluation (reset + run + score)
        python -m agent.main --evaluate --no-reset  ← evaluate without resetting sandbox

    The "-m" flag means "run this as a module" — Python will
    look for agent/main.py and execute it.
"""

import sys
from agent.config import validate_config, MAX_FIX_ATTEMPTS, GEMINI_MODEL, LOG_LEVEL
from agent.react_loop import run_react_loop


def main():
    """
    The main function. Runs when you execute this file.

    FLOW:
        Step 1 → Validate configuration (API key, etc.)
        Step 2 → Check for command-line flags
        Step 3 → Route to the correct mode:
                   default    → run the agent (ReAct loop)
                   --export-sft → export SFT training data
                   --evaluate   → run evaluation pipeline
        Step 4 → Print the final result
    """

    # ==========================================================
    # Step 1: Validate the configuration
    # ==========================================================
    try:
        validate_config()
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    # ==========================================================
    # Step 2: Check command-line flags
    # ==========================================================
    args = sys.argv[1:]

    # --export-sft: Export SFT dataset from existing logs
    if "--export-sft" in args:
        _run_sft_export(args)
        return

    # --evaluate: Full evaluation pipeline
    if "--evaluate" in args:
        _run_evaluation(args)
        return

    # ==========================================================
    # Step 3: Default mode — run the agent
    # ==========================================================
    print("=" * 60)
    print("  AUTONOMOUS DEVOPS & AUTO-FIX AGENT")
    print("=" * 60)
    print(f"  Model:        {GEMINI_MODEL}")
    print(f"  Max attempts: {MAX_FIX_ATTEMPTS}")
    print(f"  Log level:    {LOG_LEVEL}")
    print(f"  Log file:     logs/agent_runs.jsonl")
    print("=" * 60)
    print()
    print("Starting agent...")
    print()

    # ==========================================================
    # Run the ReAct loop
    # ==========================================================
    result = run_react_loop()

    # ==========================================================
    # Step 4: Print the final result
    # ==========================================================
    print()
    print("=" * 60)
    print("  AGENT RESULT")
    print("=" * 60)

    if result["success"]:
        print(f"  STATUS:   SUCCESS")
        print(f"  ATTEMPTS: {result['attempts']}")
        if result.get("branch"):
            print(f"  BRANCH:   {result['branch']}")
        print(f"  All tests are now passing.")
    else:
        print(f"  STATUS:   FAILED")
        print(f"  ATTEMPTS: {result['attempts']}")
        print(f"  Could not fix all failing tests within {MAX_FIX_ATTEMPTS} attempts.")
        print(f"  Manual intervention required.")

    print("=" * 60)

    # Return exit code: 0 = success, 1 = failure
    sys.exit(0 if result["success"] else 1)


def _run_sft_export(args: list):
    """
    Handles the --export-sft command.

    Reads agent logs and exports training data in the specified format.

    Supports:
        --export-sft              → export in Alpaca format (default)
        --export-sft --chat       → export in conversational format
        --export-sft --both       → export in both formats
    """
    from agent.sft_exporter import export_dataset_with_metadata

    print("=" * 60)
    print("  SFT DATA EXPORT")
    print("=" * 60)

    # choose format based on flags
    if "--both" in args:
        formats = ["alpaca", "conversational"]
    elif "--chat" in args:
        formats = ["conversational"]
    else:
        formats = ["alpaca"]

    for fmt in formats:
        result = export_dataset_with_metadata(format=fmt)

        if result["success"]:
            print(f"  Format:   {result['format']}")
            print(f"  Pairs:    {result['count']}")
            print(f"  File:     {result['file_path']}")
        else:
            print(f"  Export failed: {result['message']}")

    print("=" * 60)


def _run_evaluation(args: list):
    """
    Handles the --evaluate command.

    Runs the full evaluation pipeline: reset sandbox → run agent → score → report.

    Supports:
        --evaluate              → full eval (with sandbox reset)
        --evaluate --no-reset   → eval without resetting sandbox
    """
    from agent.evaluator import run_evaluation

    print("=" * 60)
    print("  AGENT EVALUATION")
    print("=" * 60)
    print(f"  Model:        {GEMINI_MODEL}")
    print(f"  Max attempts: {MAX_FIX_ATTEMPTS}")

    skip_reset = "--no-reset" in args
    if skip_reset:
        print("  Sandbox:      NOT resetting (--no-reset)")
    else:
        print("  Sandbox:      Resetting to original broken state")

    print("=" * 60)
    print()

    result = run_evaluation(reset_sandbox=not skip_reset)

    if result["success"] and result["report"].get("success"):
        print()
        print(f"  Report saved to: {result['report']['file_path']}")

    sys.exit(0 if result["scores"].get("passed", False) else 1)


# ==========================================================
# This block runs ONLY when you execute this file directly.
# It does NOT run when another file imports from this module.
#
# "python -m agent.main" triggers this block.
# "from agent.main import main" does NOT trigger this block.
# ==========================================================
if __name__ == "__main__":
    main()
