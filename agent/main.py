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
    └── This is the TOP of the call chain — nothing calls this file.
        You run it directly from the terminal.

HOW TO RUN:
    From the project root directory:
        python -m agent.main

    The "-m" flag means "run this as a module" — Python will
    look for agent/main.py and execute it.
"""

import sys
from agent.config import validate_config, MAX_FIX_ATTEMPTS, GEMINI_MODEL
from agent.react_loop import run_react_loop


def main():
    """
    The main function. Runs when you execute this file.

    FLOW:
        Step 1 → Validate configuration (API key, etc.)
        Step 2 → Print startup banner
        Step 3 → Run the ReAct loop
        Step 4 → Print the final result
    """

    # ==========================================================
    # Step 1: Validate the configuration
    # ==========================================================
    # This checks that the .env file exists and has a valid
    # API key. If not, it raises a clear error message telling
    # the user exactly what to do.
    # ==========================================================
    try:
        validate_config()
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    # ==========================================================
    # Step 2: Print startup banner
    # ==========================================================
    print("=" * 60)
    print("  AUTONOMOUS DEVOPS & AUTO-FIX AGENT")
    print("=" * 60)
    print(f"  Model:        {GEMINI_MODEL}")
    print(f"  Max attempts: {MAX_FIX_ATTEMPTS}")
    print("=" * 60)
    print()
    print("Starting agent...")
    print()

    # ==========================================================
    # Step 3: Run the ReAct loop
    # ==========================================================
    # This is where all the magic happens.
    # The loop will:
    #   1. Run tests
    #   2. If tests fail → send errors to LLM
    #   3. LLM reasons about the error
    #   4. LLM calls tools (read file, write fix, re-run tests)
    #   5. Repeat until tests pass or max attempts reached
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
        print(f"  All tests are now passing.")
    else:
        print(f"  STATUS:   FAILED")
        print(f"  ATTEMPTS: {result['attempts']}")
        print(f"  Could not fix all failing tests within {MAX_FIX_ATTEMPTS} attempts.")
        print(f"  Manual intervention required.")

    print("=" * 60)

    # Return exit code: 0 = success, 1 = failure
    sys.exit(0 if result["success"] else 1)


# ==========================================================
# This block runs ONLY when you execute this file directly.
# It does NOT run when another file imports from this module.
#
# "python -m agent.main" triggers this block.
# "from agent.main import main" does NOT trigger this block.
# ==========================================================
if __name__ == "__main__":
    main()
