"""
test_runner.py — Runs PyTest Inside the Docker Container

WHAT THIS FILE DOES:
    Executes "pytest" inside the sandbox Docker container and
    returns the full output (pass/fail results + error messages).

WHY IT EXISTS:
    The agent's entire purpose starts here. Without this file,
    the agent has no way to know if tests are passing or failing.
    This is the "trigger" that starts the fix loop.

WHERE IT SITS IN THE CODEBASE:
    tools/test_runner.py
    ├── Reads from: agent/config.py (container name, workspace path)
    ├── Used by: agent/react_loop.py (Phase 3) to check test status
    └── Depends on: Docker container running (Phase 1)

HOW IT WORKS:
    Step 1 → Builds the command: docker exec <container> python -m pytest <path> -v
    Step 2 → Sends that command to the operating system via subprocess
    Step 3 → subprocess runs it → pytest runs INSIDE the container
    Step 4 → Captures stdout (normal output) and stderr (error output)
    Step 5 → Returns both as a dictionary with pass/fail status
"""

import subprocess
from agent.config import SANDBOX_CONTAINER_NAME, SANDBOX_WORKSPACE_PATH


def run_tests(test_path: str = "tests/") -> dict:
    """
    Runs pytest inside the sandbox container.

    Parameters:
        test_path (str): Path to the test file or folder, relative
                         to the workspace root inside the container.
                         Default: "tests/" (runs all tests).

    Returns:
        dict with three keys:
            "success"  (bool)  — True if ALL tests passed, False if any failed
            "output"   (str)   — The full pytest output (what you'd see in terminal)
            "exit_code"(int)   — 0 = all passed, 1 = some failed, 2 = error in test code
    """

    # --------------------------------------------------
    # Step 1: Build the command
    # --------------------------------------------------
    # "docker exec" means: run this command inside an already-running container
    # SANDBOX_CONTAINER_NAME = "devops-agent-sandbox" (from config.py)
    # SANDBOX_WORKSPACE_PATH = "/workspace" (from config.py)
    # "-m pytest" means: run pytest as a Python module
    # "-v" means: verbose — show each test name and its result
    # "--tb=short" means: show short tracebacks — enough detail for the LLM
    #                     to understand the error without overwhelming it
    # --------------------------------------------------
    full_test_path = f"{SANDBOX_WORKSPACE_PATH}/{test_path}"

    command = [
        "docker", "exec",
        SANDBOX_CONTAINER_NAME,
        "python", "-m", "pytest",
        full_test_path,
        "-v",
        "--tb=short",
        "--no-header",
    ]

    # --------------------------------------------------
    # Step 2: Execute the command
    # --------------------------------------------------
    # subprocess.run() sends the command to the operating system.
    #
    # capture_output=True → captures stdout and stderr instead of
    #                        printing them to your terminal
    # text=True           → returns output as a string (not raw bytes)
    # timeout=60          → if pytest hangs for more than 60 seconds,
    #                        kill it and raise a TimeoutError
    # --------------------------------------------------
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # --------------------------------------------------
        # Step 3: Package the result
        # --------------------------------------------------
        # result.returncode:
        #   0 = all tests passed
        #   1 = some tests failed
        #   2 = pytest itself crashed (syntax error in test file, etc.)
        #   5 = no tests were found
        #
        # result.stdout = the normal output (test names, pass/fail)
        # result.stderr = error output (Python tracebacks, warnings)
        # --------------------------------------------------
        combined_output = result.stdout
        if result.stderr:
            combined_output += "\n--- STDERR ---\n" + result.stderr

        return {
            "success": result.returncode == 0,
            "output": combined_output.strip(),
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "ERROR: pytest timed out after 60 seconds. "
                      "Possible infinite loop in the code under test.",
            "exit_code": -1,
        }

    except FileNotFoundError:
        return {
            "success": False,
            "output": "ERROR: Docker is not installed or not in PATH. "
                      "Make sure Docker Desktop is running.",
            "exit_code": -2,
        }

    except Exception as e:
        return {
            "success": False,
            "output": f"ERROR: Unexpected error running tests: {str(e)}",
            "exit_code": -3,
        }
