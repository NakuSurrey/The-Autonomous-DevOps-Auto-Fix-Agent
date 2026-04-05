"""
prompt_templates.py — All Prompts and Tool Definitions

WHAT THIS FILE DOES:
    Stores every prompt the agent sends to the Gemini LLM.
    Also defines the "tool declarations" — the descriptions that
    tell Gemini what tools it can call and what parameters each
    tool accepts.

WHY IT EXISTS:
    Keeping all prompts in one file makes them easy to find, edit,
    and version-control. If a prompt is scattered across 5 files,
    changing the agent's behavior becomes a nightmare.

WHERE IT SITS IN THE CODEBASE:
    agent/prompt_templates.py
    ├── Used by: agent/llm_client.py (sends these prompts to Gemini)
    ├── Used by: agent/react_loop.py (uses TOOL_NAME_LIST to validate tool calls)
    └── Depends on: google.genai.types (for FunctionDeclaration and Tool types)
"""

from google.genai import types


# ==========================================================
# SYSTEM PROMPT
# ==========================================================
# This is the "personality" and "instructions" for the LLM.
# It is sent ONCE at the start of every conversation.
# It tells Gemini:
#   - Who it is (an autonomous DevOps agent)
#   - What it can do (read files, write files, run tests, run git)
#   - How to think (ReAct: Thought → Action → Observation)
#   - What rules to follow (max attempts, safety rules)
# ==========================================================

SYSTEM_PROMPT = """You are an Autonomous DevOps & Auto-Fix Agent.

YOUR JOB:
You monitor a Python codebase inside a Docker container. When tests fail,
you analyze the errors, read the broken code, write fixes, and verify
your fixes by re-running the tests.

HOW YOU THINK (ReAct Framework):
You follow a strict loop:
1. THOUGHT: Analyze the current situation. What do you know? What is broken? What should you do next?
2. ACTION: Call exactly ONE tool to gather information or make a change.
3. OBSERVATION: Read the result of your action.
4. Repeat from step 1 until all tests pass or you run out of attempts.

AVAILABLE TOOLS:
- run_tests(test_path): Run pytest on the given path. Returns pass/fail + error output.
- read_file(file_path): Read a file from the workspace. Returns the file contents.
- write_file(file_path, content): Write content to a file. Replaces the entire file.

RULES YOU MUST FOLLOW:
1. ALWAYS think before acting. Never call a tool without explaining your reasoning first.
2. Call exactly ONE tool per turn. Never call multiple tools at once.
3. When you call write_file, you must write the COMPLETE file contents — not just the changed lines. The tool replaces the entire file.
4. After writing a fix, ALWAYS call run_tests to verify it worked.
5. If your fix did not work, read the NEW error output carefully. Do not repeat the same fix.
6. Never modify the test files. The tests define the correct behavior. Only fix the source code.
7. Never delete files or create new files. Only modify existing source files.
8. Keep your fixes minimal. Change only what is necessary to make the tests pass.

FILE PATHS:
All file paths are relative to the workspace root. Examples:
- "calculator.py" (the source file)
- "tests/test_calculator.py" (the test file — DO NOT MODIFY)

RESPONSE FORMAT:
Always structure your response as:
THOUGHT: [your reasoning about the current situation]
Then call exactly one tool.
"""


# ==========================================================
# TOOL DECLARATIONS
# ==========================================================
# These tell Gemini what tools it can call.
# Each tool has:
#   - name: what the LLM calls it (e.g., "run_tests")
#   - description: what it does (the LLM reads this to decide when to use it)
#   - parameters: what arguments it accepts (name, type, required)
#
# Gemini uses these declarations to generate "function calls"
# in its response. Instead of responding with text, it responds
# with: "I want to call run_tests with test_path='tests/'"
#
# The format below follows Google Gemini's function calling spec.
# ==========================================================

# --------------------------------------------------
# Each FunctionDeclaration tells Gemini about one tool:
#   - name: what the LLM calls it (e.g., "run_tests")
#   - description: what it does (LLM reads this to decide when to use it)
#   - parameters: what arguments it accepts (name, type, required)
#
# We use the new google.genai.types classes (not raw dicts).
# --------------------------------------------------

_run_tests_declaration = types.FunctionDeclaration(
    name="run_tests",
    description=(
        "Runs pytest on the specified test path inside the Docker sandbox. "
        "Returns the full test output including pass/fail results and error messages. "
        "Use this to check if tests are passing or to verify a fix after writing code."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "test_path": types.Schema(
                type="STRING",
                description=(
                    "Path to the test file or directory, relative to the workspace root. "
                    "Example: 'tests/' to run all tests, or 'tests/test_calculator.py' "
                    "to run a specific file."
                ),
            ),
        },
        required=["test_path"],
    ),
)

_read_file_declaration = types.FunctionDeclaration(
    name="read_file",
    description=(
        "Reads the contents of a file inside the Docker sandbox. "
        "Returns the full file contents as text. "
        "Use this to examine source code when you need to understand what a function does "
        "or to find the bug causing a test failure."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "file_path": types.Schema(
                type="STRING",
                description=(
                    "Path to the file to read, relative to the workspace root. "
                    "Example: 'calculator.py' or 'tests/test_calculator.py'"
                ),
            ),
        },
        required=["file_path"],
    ),
)

_write_file_declaration = types.FunctionDeclaration(
    name="write_file",
    description=(
        "Writes content to a file inside the Docker sandbox, replacing the entire file. "
        "You must provide the COMPLETE file contents, not just the changed lines. "
        "Use this to apply your fix after analyzing the bug. "
        "IMPORTANT: Never use this on test files. Only modify source code files."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "file_path": types.Schema(
                type="STRING",
                description=(
                    "Path to the file to write, relative to the workspace root. "
                    "Example: 'calculator.py'"
                ),
            ),
            "content": types.Schema(
                type="STRING",
                description=(
                    "The complete new file contents. Must include ALL lines of the file, "
                    "not just the changed part."
                ),
            ),
        },
        required=["file_path", "content"],
    ),
)

# --------------------------------------------------
# AGENT_TOOLS: A single Tool object containing all function declarations.
# This is what gets passed to the Gemini API config.
# --------------------------------------------------
AGENT_TOOLS = types.Tool(
    function_declarations=[
        _run_tests_declaration,
        _read_file_declaration,
        _write_file_declaration,
    ]
)

# --------------------------------------------------
# TOOL_NAME_LIST: A simple list of valid tool names.
# Used by react_loop.py to validate that the LLM is calling
# a real tool and not hallucinating a tool name.
# --------------------------------------------------
TOOL_NAME_LIST = ["run_tests", "read_file", "write_file"]


# ==========================================================
# INITIAL USER MESSAGE TEMPLATE
# ==========================================================
# This is the first message sent to Gemini after the system prompt.
# It contains the test results that triggered the agent.
# The {test_output} placeholder gets replaced with the actual
# pytest output at runtime.
# ==========================================================

INITIAL_MESSAGE_TEMPLATE = """The following pytest run has FAILED. Your job is to fix the code so all tests pass.

TEST OUTPUT:
{test_output}

Begin by analyzing the errors. Then read the relevant source file(s) to understand the bugs. Then write fixes and verify them by re-running the tests.

Remember:
- Fix the source code, NOT the tests.
- Write the COMPLETE file when using write_file.
- Verify every fix by running the tests again.
"""


# ==========================================================
# OBSERVATION MESSAGE TEMPLATE
# ==========================================================
# After the agent calls a tool, we send the tool's result
# back to the LLM using this template.
# The {tool_name} and {result} placeholders get replaced
# at runtime.
# ==========================================================

OBSERVATION_TEMPLATE = """OBSERVATION from {tool_name}:
{result}

Continue your analysis. If tests are not yet passing, determine what to do next.
If all tests pass, respond with exactly: ALL_TESTS_PASSED
"""
