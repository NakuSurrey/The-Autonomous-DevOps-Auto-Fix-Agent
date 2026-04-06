"""
evaluation_runner.py — Resets the Sandbox for Clean Evaluation Runs

WHAT THIS FILE DOES:
    Rebuilds the Docker sandbox container so the calculator.py is
    back to its original broken state. This lets the agent start
    fresh every evaluation run.

WHY IT EXISTS:
    After the agent fixes the bugs in calculator.py, the container
    has the fixed code. If you run the agent again, tests already
    pass — there is nothing to fix. To evaluate the agent properly,
    the sandbox must be reset to the original broken state before
    each run.

WHERE IT SITS IN THE CODEBASE:
    tools/evaluation_runner.py
    ├── Reads from: agent/config.py (container name)
    ├── Uses: Docker CLI (docker-compose down + up --build)
    ├── Used by: agent/evaluator.py (called before each eval run)
    └── Depends on: Dockerfile and sandbox/ files existing

HOW THE RESET WORKS:
    Step 1 → docker-compose down — stops and removes the current container
    Step 2 → docker-compose up -d --build — rebuilds from the Dockerfile
    Step 3 → The Dockerfile COPYs the original sandbox/ files into the container
    Step 4 → The container now has the original broken calculator.py
    Step 5 → A fresh git init + commit happens inside the container
    Step 6 → The agent can now run against a clean, broken codebase

WHY WE REBUILD INSTEAD OF GIT RESET:
    Option A: git reset --hard inside the container
      → Faster, but only undoes file changes.
      → Does not undo any pip installs or system changes the agent might have made.

    Option B: Rebuild the container from scratch
      → Slower (10-20 seconds), but guarantees a completely clean state.
      → The Dockerfile starts from the base image every time.
      → Chose this because correctness matters more than speed in evaluation.
"""

import subprocess
import time

from agent.config import SANDBOX_CONTAINER_NAME, PROJECT_ROOT


def reset_sandbox() -> dict:
    """
    Tears down and rebuilds the Docker sandbox container.

    Returns:
        dict with:
            "success" (bool): True if the container is running after reset
            "message" (str):  What happened
            "duration_seconds" (float): How long the reset took

    HOW IT WORKS:
        Step 1 → Run docker-compose down (stop + remove container)
        Step 2 → Run docker-compose up -d --build (rebuild + start)
        Step 3 → Wait briefly for the container to initialize
        Step 4 → Verify the container is running
        Step 5 → Return the result
    """
    start_time = time.time()

    # ==========================================================
    # Step 1: Stop and remove the current container
    # ==========================================================
    # "docker-compose down" stops the container and removes it.
    # This deletes everything inside the container — all file
    # changes, git history, installed packages — everything.
    # ==========================================================
    try:
        down_result = subprocess.run(
            ["docker-compose", "down"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        if down_result.returncode != 0:
            # "down" can fail if the container doesn't exist — that's ok
            # we'll try to build anyway
            pass

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "docker-compose down timed out after 30 seconds.",
            "duration_seconds": time.time() - start_time,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "docker-compose not found. Is Docker installed?",
            "duration_seconds": time.time() - start_time,
        }

    # ==========================================================
    # Step 2: Rebuild and start the container
    # ==========================================================
    # "docker-compose up -d --build" does three things:
    #   --build  → rebuild the image from the Dockerfile
    #   -d       → run in detached mode (background)
    #   up       → start the container
    #
    # The Dockerfile COPYs the original sandbox/ files, so the
    # container starts with the original broken calculator.py.
    # ==========================================================
    try:
        up_result = subprocess.run(
            ["docker-compose", "up", "-d", "--build"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        if up_result.returncode != 0:
            return {
                "success": False,
                "message": f"docker-compose up failed: {up_result.stderr}",
                "duration_seconds": time.time() - start_time,
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "docker-compose up --build timed out after 120 seconds.",
            "duration_seconds": time.time() - start_time,
        }

    # ==========================================================
    # Step 3: Wait briefly for initialization
    # ==========================================================
    # The container needs a moment to fully start. The Dockerfile
    # runs git init + git commit during build, but the container
    # process (tail -f /dev/null) needs a second to be ready.
    # ==========================================================
    time.sleep(2)

    # ==========================================================
    # Step 4: Verify the container is running
    # ==========================================================
    # "docker ps --filter" checks if the container exists and is running.
    # ==========================================================
    try:
        verify_result = subprocess.run(
            [
                "docker", "ps",
                "--filter", f"name={SANDBOX_CONTAINER_NAME}",
                "--format", "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        status = verify_result.stdout.strip()
        is_running = "Up" in status

        duration = time.time() - start_time

        if is_running:
            return {
                "success": True,
                "message": f"Sandbox reset complete. Container is running. ({duration:.1f}s)",
                "duration_seconds": round(duration, 1),
            }
        else:
            return {
                "success": False,
                "message": f"Container is not running after rebuild. Status: '{status}'",
                "duration_seconds": round(duration, 1),
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to verify container status: {e}",
            "duration_seconds": time.time() - start_time,
        }


def quick_reset_sandbox() -> dict:
    """
    Fast reset using git inside the container (no rebuild).

    This is faster than a full rebuild but only resets file changes.
    Use this when you are sure the agent did not install packages
    or modify system files.

    Returns:
        dict: Same structure as reset_sandbox().

    HOW IT WORKS:
        Step 1 → Run "git checkout -- ." inside the container
                 This reverts all tracked files to their last committed state
        Step 2 → Run "git clean -fd" inside the container
                 This removes any new untracked files the agent created
    """
    start_time = time.time()

    try:
        # revert all tracked files to the initial commit
        checkout_result = subprocess.run(
            [
                "docker", "exec", SANDBOX_CONTAINER_NAME,
                "git", "checkout", "--", ".",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # remove any untracked files
        clean_result = subprocess.run(
            [
                "docker", "exec", SANDBOX_CONTAINER_NAME,
                "git", "clean", "-fd",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        duration = time.time() - start_time

        if checkout_result.returncode == 0:
            return {
                "success": True,
                "message": f"Quick reset done — files reverted to initial commit. ({duration:.1f}s)",
                "duration_seconds": round(duration, 1),
            }
        else:
            return {
                "success": False,
                "message": f"git checkout failed: {checkout_result.stderr}",
                "duration_seconds": round(duration, 1),
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Quick reset timed out.",
            "duration_seconds": time.time() - start_time,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "Docker not found. Is Docker installed?",
            "duration_seconds": time.time() - start_time,
        }
