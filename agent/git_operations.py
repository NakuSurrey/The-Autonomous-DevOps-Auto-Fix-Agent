"""
git_operations.py — High-Level Git Workflows

WHAT THIS FILE DOES:
    Combines low-level git commands from tools/git_manager.py into
    complete workflows. The main workflow is: after the agent fixes
    all tests, create a branch, stage the changes, and commit.

WHY IT EXISTS:
    tools/git_manager.py has one function per git command.
    But a complete git workflow needs multiple commands in sequence:
        1. Create a branch
        2. Stage files
        3. Commit with a message

    Without this file, the react_loop would have to call each
    git function individually and handle errors between each step.
    This file packages the whole workflow into one function call.

WHERE IT SITS IN THE CODEBASE:
    agent/git_operations.py
    ├── Reads from: tools/git_manager.py (low-level git functions)
    ├── Reads from: agent/logger.py (logs every git step)
    ├── Used by: agent/react_loop.py (called after all tests pass)
    └── Phase 6 will add validation checks before commits are allowed

HOW THE COMMIT WORKFLOW WORKS:
    Step 1 → Check git status (see what files changed)
    Step 2 → Create a new branch named "auto-fix/run-<run_id>"
    Step 3 → Stage all changed files (git add .)
    Step 4 → Commit with a message describing what was fixed
    Step 5 → Return the branch name and commit result
"""

from agent.guardrails import validate_git_commit
from agent.logger import AgentLogger
from tools.git_manager import (
    git_status,
    git_diff,
    git_create_branch,
    git_add,
    git_commit,
    git_log,
)


def commit_fix(run_id: str, attempt: int, logger: AgentLogger) -> dict:
    """
    Creates a branch and commits the agent's fix.

    Called by react_loop.py after all tests pass.

    Parameters:
        run_id (str):           The unique ID for this agent run.
                                Used in the branch name: "auto-fix/run-<run_id>"
        attempt (int):          Which attempt number succeeded.
                                Included in the commit message.
        logger (AgentLogger):   The logger instance for this run.
                                Every git step is logged.

    Returns:
        dict with:
            "success"     (bool) — True if branch + commit succeeded
            "branch_name" (str)  — The name of the created branch
            "message"     (str)  — Description of what happened (success or error)

    HOW IT WORKS:
        Step 1 → Run git status to see what changed
        Step 2 → Run git diff to capture the actual changes
        Step 3 → Create a new branch
        Step 4 → Stage all changes
        Step 5 → Commit with a descriptive message
        Step 6 → Run git log to confirm the commit exists
    """

    branch_name = f"auto-fix/run-{run_id}"

    # ==========================================================
    # Step 1: Check git status
    # ==========================================================
    # See what files the agent modified during the fix.
    # If nothing changed, there is nothing to commit.
    # ==========================================================
    logger.log("system", "Checking git status before commit...")
    status_result = git_status()

    if not status_result["success"]:
        logger.log_error(
            f"git status failed: {status_result['output']}",
            context="commit_fix"
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": f"git status failed: {status_result['output']}",
        }

    # Check if there are actually changes to commit
    if "nothing to commit" in status_result["output"]:
        logger.log(
            "warning",
            "No changes detected. Nothing to commit."
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": "No changes to commit. Working tree is clean.",
        }

    logger.log(
        "system",
        f"Files changed:\n{status_result['output']}"
    )

    # ==========================================================
    # Step 1b: GUARDRAIL — Validate changed files before commit
    # ==========================================================
    # Check that the agent did not modify protected files
    # (test files, config files, agent source code).
    # If protected files were changed, block the commit.
    # ==========================================================
    guard_result = validate_git_commit(status_result["output"])

    if not guard_result["allowed"]:
        logger.log_error(
            f"Git commit blocked by guardrail: {guard_result['reason']}",
            context="commit_fix_guardrail"
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": guard_result["reason"],
        }

    logger.log("system", "Guardrail check passed. Safe to commit.")

    # ==========================================================
    # Step 2: Capture the diff for the log
    # ==========================================================
    # Save a record of exactly what the agent changed.
    # This goes into the log file — not into the commit.
    # ==========================================================
    logger.log("system", "Capturing diff of changes...")
    diff_result = git_diff()

    if diff_result["success"] and diff_result["output"]:
        logger.log(
            "system",
            f"Changes made:\n{diff_result['output'][:3000]}"
        )

    # ==========================================================
    # Step 3: Create a new branch
    # ==========================================================
    # Branch naming convention: "auto-fix/run-<run_id>"
    # The "auto-fix/" prefix makes it clear this branch was
    # created by the agent, not by a human developer.
    # The run_id lets you match the branch to a specific log file.
    # ==========================================================
    logger.log("system", f"Creating branch: {branch_name}")
    branch_result = git_create_branch(branch_name)

    if not branch_result["success"]:
        logger.log_error(
            f"Failed to create branch '{branch_name}': {branch_result['output']}",
            context="commit_fix"
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": f"Failed to create branch: {branch_result['output']}",
        }

    logger.log("system", f"Branch created: {branch_result['output']}")

    # ==========================================================
    # Step 4: Stage all changed files
    # ==========================================================
    # git add "." means "stage everything in the current directory."
    # Since the agent only modifies source files (never test files
    # or config files), this is safe. Phase 6 will add guardrails
    # to verify this before staging.
    # ==========================================================
    logger.log("system", "Staging all changes...")
    add_result = git_add(".")

    if not add_result["success"]:
        logger.log_error(
            f"git add failed: {add_result['output']}",
            context="commit_fix"
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": f"git add failed: {add_result['output']}",
        }

    logger.log("system", "All changes staged.")

    # ==========================================================
    # Step 5: Commit with a descriptive message
    # ==========================================================
    # The commit message format:
    #   Line 1: "fix: auto-fix by DevOps Agent (run <run_id>)"
    #   Line 2: blank
    #   Line 3: "Resolved failing tests in <N> attempt(s)."
    #   Line 4: "Automated fix applied by the Autonomous DevOps Agent."
    #
    # The "fix:" prefix follows Conventional Commits format.
    # This is a widely used standard in professional codebases.
    # ==========================================================
    commit_message = (
        f"fix: auto-fix by DevOps Agent (run {run_id})\n\n"
        f"Resolved failing tests in {attempt} attempt(s).\n"
        f"Automated fix applied by the Autonomous DevOps Agent."
    )

    logger.log("system", f"Committing with message:\n{commit_message}")
    commit_result = git_commit(commit_message)

    if not commit_result["success"]:
        logger.log_error(
            f"git commit failed: {commit_result['output']}",
            context="commit_fix"
        )
        return {
            "success": False,
            "branch_name": branch_name,
            "message": f"git commit failed: {commit_result['output']}",
        }

    logger.log("system", f"Commit successful: {commit_result['output']}")

    # ==========================================================
    # Step 6: Verify with git log
    # ==========================================================
    # Read the most recent commit to confirm it was saved.
    # This is a safety check — belt and suspenders.
    # ==========================================================
    logger.log("system", "Verifying commit with git log...")
    log_result = git_log(count=1)

    if log_result["success"]:
        logger.log("system", f"Latest commit: {log_result['output']}")

    # ==========================================================
    # Done — return success
    # ==========================================================
    return {
        "success": True,
        "branch_name": branch_name,
        "message": (
            f"Fix committed successfully.\n"
            f"Branch: {branch_name}\n"
            f"Commit: {commit_result['output']}"
        ),
    }
