"""
react_loop.py — The ReAct Engine (Reasoning + Acting Loop)

WHAT THIS FILE DOES:
    Orchestrates the entire fix cycle:
    Run tests → See failure → Think → Act → Observe → Repeat

WHY IT EXISTS:
    This is the CORE of the agent. Without it, the LLM can think
    but has no loop to keep going. This file connects the LLM's
    brain (llm_client) to the agent's hands (tools) and runs the
    loop until tests pass or max attempts are reached.

WHERE IT SITS IN THE CODEBASE:
    agent/react_loop.py
    ├── Reads from: agent/config.py (MAX_FIX_ATTEMPTS)
    ├── Reads from: agent/llm_client.py (LLMClient class)
    ├── Reads from: agent/prompt_templates.py (message templates)
    ├── Calls: tools/test_runner.py (run_tests)
    ├── Calls: tools/file_reader.py (read_file)
    ├── Calls: tools/file_writer.py (write_file)
    ├── Used by: agent/main.py (entry point calls run_react_loop)
    └── Sends to: Phase 4 will add logging hooks into this loop

HOW THE LOOP WORKS:
    Step 1  → Run tests → capture the failure output
    Step 2  → Start a chat with the LLM
    Step 3  → Send the failure output to the LLM
    Step 4  → LLM responds with either TEXT (thought) or FUNCTION_CALL (action)
    Step 5  → If FUNCTION_CALL: execute the tool, send result back to LLM
    Step 6  → If TEXT contains "ALL_TESTS_PASSED": we are done
    Step 7  → If attempt count < MAX: go back to Step 4
    Step 8  → If attempt count >= MAX: give up
"""

from agent.config import MAX_FIX_ATTEMPTS
from agent.llm_client import LLMClient
from agent.prompt_templates import INITIAL_MESSAGE_TEMPLATE, OBSERVATION_TEMPLATE
from tools.test_runner import run_tests
from tools.file_reader import read_file
from tools.file_writer import write_file


# ==========================================================
# TOOL REGISTRY
# ==========================================================
# Maps tool names (strings the LLM outputs) to actual Python
# functions. When the LLM says "call run_tests", we look up
# "run_tests" in this dictionary and call the matching function.
# ==========================================================

TOOL_REGISTRY = {
    "run_tests": run_tests,
    "read_file": read_file,
    "write_file": write_file,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    Executes a tool by name and returns the result as a string.

    HOW IT WORKS:
        Step 1 → Look up the tool name in TOOL_REGISTRY
        Step 2 → Call the function with the provided arguments
        Step 3 → Convert the result dict to a readable string
        Step 4 → Return the string (this gets sent back to the LLM)

    Parameters:
        tool_name (str): Name of the tool (e.g., "run_tests")
        tool_args (dict): Arguments for the tool (e.g., {"test_path": "tests/"})

    Returns:
        str: The tool's result as a human-readable string.
    """

    # --------------------------------------------------
    # Step 1: Check if the tool exists
    # --------------------------------------------------
    if tool_name not in TOOL_REGISTRY:
        return f"ERROR: Unknown tool '{tool_name}'. Available tools: {list(TOOL_REGISTRY.keys())}"

    # --------------------------------------------------
    # Step 2: Get the function and call it
    # --------------------------------------------------
    tool_function = TOOL_REGISTRY[tool_name]

    try:
        result = tool_function(**tool_args)
    except TypeError as e:
        return f"ERROR: Bad arguments for '{tool_name}': {str(e)}"
    except Exception as e:
        return f"ERROR: Tool '{tool_name}' crashed: {str(e)}"

    # --------------------------------------------------
    # Step 3: Convert the result to a readable string
    # --------------------------------------------------
    # Each tool returns a dict. We format it into a string
    # the LLM can easily parse.
    # --------------------------------------------------
    if tool_name == "run_tests":
        status = "PASSED" if result["success"] else "FAILED"
        return f"Test result: {status}\n\n{result['output']}"

    elif tool_name == "read_file":
        if result["success"]:
            return f"Contents of {result['file_path']}:\n\n{result['content']}"
        else:
            return result["content"]

    elif tool_name == "write_file":
        return result["message"]

    else:
        return str(result)


def run_react_loop() -> dict:
    """
    Runs the full ReAct loop: Test → Think → Act → Observe → Repeat

    Returns:
        dict with:
            "success"   (bool)  — True if all tests pass, False if gave up
            "attempts"  (int)   — How many loop iterations were used
            "history"   (list)  — List of every Thought, Action, Observation

    THE FULL FLOW:
        Step 1  → Run tests
        Step 2  → If tests pass already → return success (nothing to fix)
        Step 3  → Start LLM chat
        Step 4  → Send failure output to LLM
        Step 5  → Enter the loop:
                    a) LLM responds with function_call → execute tool → send result back
                    b) LLM responds with text → check if ALL_TESTS_PASSED
                    c) If not done → loop again
                    d) If max attempts → give up
    """

    # --------------------------------------------------
    # This list records everything that happens in the loop.
    # Each entry is a dict with "type" and "content".
    # Phase 4 will use this for structured logging.
    # --------------------------------------------------
    history = []

    def log_event(event_type: str, content: str):
        """Adds an event to the history list."""
        entry = {"type": event_type, "content": content}
        history.append(entry)
        # Print to terminal so we can watch the agent work in real time
        print(f"\n{'='*60}")
        print(f"[{event_type.upper()}]")
        print(f"{'='*60}")
        print(content)

    # ==========================================================
    # Step 1: Run the initial tests
    # ==========================================================
    log_event("system", "Running initial test suite...")
    initial_test_result = run_tests(test_path="tests/")

    # ==========================================================
    # Step 2: If tests already pass, nothing to fix
    # ==========================================================
    if initial_test_result["success"]:
        log_event("system", "All tests already pass. Nothing to fix.")
        return {
            "success": True,
            "attempts": 0,
            "history": history,
        }

    log_event("test_failure", initial_test_result["output"])

    # ==========================================================
    # Step 3: Start the LLM chat
    # ==========================================================
    log_event("system", "Starting LLM conversation...")
    client = LLMClient()
    client.start_chat()

    # ==========================================================
    # Step 4: Send the initial failure to the LLM
    # ==========================================================
    initial_message = INITIAL_MESSAGE_TEMPLATE.format(
        test_output=initial_test_result["output"]
    )

    log_event("user_message", "Sending test failures to LLM...")
    response = client.send_message(initial_message)

    # ==========================================================
    # Step 5: Enter the ReAct loop
    # ==========================================================
    attempt = 0

    while attempt < MAX_FIX_ATTEMPTS:
        attempt += 1
        log_event("system", f"--- Attempt {attempt} of {MAX_FIX_ATTEMPTS} ---")

        # ------------------------------------------------------
        # Handle the LLM's response
        # ------------------------------------------------------
        # The LLM can respond in two ways:
        #   a) function_call → it wants to use a tool
        #   b) text → it is thinking or reporting results
        #
        # We keep processing responses until we get a text
        # response (which means the LLM is done acting for
        # this turn) or we hit the max attempts.
        # ------------------------------------------------------

        # Inner loop: handle chains of function calls
        # The LLM might call multiple tools in sequence
        # (read file → write fix → run tests) before giving
        # a text response.
        max_tool_calls_per_attempt = 10
        tool_calls_this_attempt = 0

        while tool_calls_this_attempt < max_tool_calls_per_attempt:

            if response["type"] == "function_call":
                # ------------------------------------------
                # LLM wants to call a tool
                # ------------------------------------------
                tool_name = response["content"]["name"]
                tool_args = response["content"]["args"]

                log_event(
                    "action",
                    f"LLM called: {tool_name}({tool_args})"
                )

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)

                log_event(
                    "observation",
                    f"Result of {tool_name}:\n{tool_result[:2000]}"  # Truncate very long outputs
                )

                # Check if the tool was run_tests and it passed
                if tool_name == "run_tests" and "PASSED" in tool_result and "FAILED" not in tool_result:
                    log_event("system", "ALL TESTS PASSED! Fix successful.")
                    return {
                        "success": True,
                        "attempts": attempt,
                        "history": history,
                    }

                # Send the tool result back to the LLM
                response = client.send_tool_result(tool_name, tool_result)
                tool_calls_this_attempt += 1

            elif response["type"] == "text":
                # ------------------------------------------
                # LLM sent a text response
                # ------------------------------------------
                text_content = response["content"]
                log_event("thought", text_content)

                # Check if the LLM says all tests passed
                if "ALL_TESTS_PASSED" in text_content:
                    log_event("system", "LLM reports all tests passed.")
                    return {
                        "success": True,
                        "attempts": attempt,
                        "history": history,
                    }

                # Send a follow-up message to keep the loop going
                response = client.send_message(
                    "Continue. If you need to take an action, call a tool. "
                    "If all tests pass, respond with ALL_TESTS_PASSED."
                )
                break  # Break inner loop, go to next attempt

            else:
                # ------------------------------------------
                # Unexpected response type
                # ------------------------------------------
                log_event(
                    "error",
                    f"Unexpected response type: {response['type']}"
                )
                break

        # Safety check: too many tool calls in one attempt
        if tool_calls_this_attempt >= max_tool_calls_per_attempt:
            log_event(
                "warning",
                f"Hit max tool calls ({max_tool_calls_per_attempt}) in one attempt. "
                "Moving to next attempt."
            )
            response = client.send_message(
                "You have made too many tool calls in this round. "
                "Please summarize your progress and try a different approach."
            )

    # ==========================================================
    # Step 6: Max attempts reached — give up
    # ==========================================================
    log_event(
        "system",
        f"GIVING UP after {MAX_FIX_ATTEMPTS} attempts. "
        "Could not fix all failing tests."
    )

    return {
        "success": False,
        "attempts": MAX_FIX_ATTEMPTS,
        "history": history,
    }
