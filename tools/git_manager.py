"""
git_manager.py — Runs Git Commands Inside the Docker Container

WHAT THIS FILE DOES:
    Executes git commands inside the sandbox container.
    Provides specific functions for each git operation the agent needs:
    create branch, stage files, commit, view diff, view status.

WHY IT EXISTS:
    After the agent fixes a bug and tests pass, it needs to:
    1. Create a new branch (so fixes are separate from main)
    2. Stage the changed files (tell git which files to include)
    3. View the diff (review what it changed — self-reflection step)
    4. Commit with a descriptive message (save the fix permanently)

    Without this file, the agent can fix code but cannot record its work.

WHERE IT SITS IN THE CODEBASE:
    tools/git_manager.py
    ├── Reads from: agent/config.py (container name, workspace path)
    ├── Used by: agent/react_loop.py (Phase 3) after tests pass
    └── Depends on: Docker container running with git initialized (Phase 1)

HOW IT WORKS:
    Every function follows the same pattern:
    Step 1 → Build a "docker exec <container> git <command>" string
    Step 2 → subprocess sends it into the container
    Step 3 → git runs inside the container
    Step 4 → Capture and return the output
"""

import subprocess
from agent.config import SANDBOX_CONTAINER_NAME, SANDBOX_WORKSPACE_PATH


# --------------------------------------------------
# PRIVATE HELPER: Runs any git command inside the container
# --------------------------------------------------
# This function is "private" (starts with underscore).
# Other files should NOT call this directly.
# They should use the specific public functions below.
# --------------------------------------------------
def _run_git_command(args: list[str]) -> dict:
    """
    Runs a git command inside the sandbox container.

    Parameters:
        args (list[str]): The git arguments. Example: ["status"]
                          becomes "git -C /workspace status"

    Returns:
        dict with:
            "success" (bool) — True if git command succeeded
            "output"  (str)  — The git output or error message
    """

    # "git -C /workspace" means: run git as if you are inside /workspace
    # This is needed because "docker exec" starts in the container's
    # WORKDIR, but we want to be explicit about the path.
    command = [
        "docker", "exec",
        SANDBOX_CONTAINER_NAME,
        "git", "-C", SANDBOX_WORKSPACE_PATH,
    ] + args

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        combined_output = result.stdout
        if result.stderr:
            combined_output += "\n" + result.stderr

        return {
            "success": result.returncode == 0,
            "output": combined_output.strip(),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "ERROR: Git command timed out after 30 seconds.",
        }

    except Exception as e:
        return {
            "success": False,
            "output": f"ERROR: Unexpected error running git: {str(e)}",
        }


# ==========================================================
# PUBLIC FUNCTIONS — These are what the agent calls
# ==========================================================


def git_status() -> dict:
    """
    Returns the current git status inside the container.
    Shows which files are modified, staged, or untracked.
    """
    return _run_git_command(["status"])


def git_diff() -> dict:
    """
    Returns the diff of all unstaged changes.
    Shows exactly what lines were added/removed in each file.
    This is the "self-reflection" step — the agent reviews
    what it changed before committing.
    """
    return _run_git_command(["diff"])


def git_diff_staged() -> dict:
    """
    Returns the diff of staged changes (files added with git add).
    Used after staging to review what will be committed.
    """
    return _run_git_command(["diff", "--staged"])


def git_create_branch(branch_name: str) -> dict:
    """
    Creates a new branch and switches to it.

    Parameters:
        branch_name (str): Name of the new branch.
                           Example: "fix/subtract-bug"
    """
    return _run_git_command(["checkout", "-b", branch_name])


def git_add(file_path: str = ".") -> dict:
    """
    Stages a file (or all files) for commit.

    Parameters:
        file_path (str): File to stage, relative to workspace.
                         Default: "." (stage everything).
                         Example: "calculator.py"
    """
    return _run_git_command(["add", file_path])


def git_commit(message: str) -> dict:
    """
    Commits all staged changes with the given message.

    Parameters:
        message (str): The commit message.
                       Example: "fix: correct subtract() to use minus operator"
    """
    return _run_git_command(["commit", "-m", message])


def git_log(count: int = 5) -> dict:
    """
    Returns the last N commit messages.

    Parameters:
        count (int): How many recent commits to show. Default: 5.
    """
    return _run_git_command(["log", f"--oneline", f"-{count}"])
