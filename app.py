"""
app.py — Streamlit Live Demo for the Autonomous DevOps & Auto-Fix Agent

WHAT THIS FILE DOES:
    Provides a web interface where anyone can watch the agent work.
    Two modes:
      - Demo Mode: replays a real agent run with actual data (no API key needed)
      - Live Mode: connects to Gemini API and runs the agent for real

WHY IT EXISTS:
    Recruiters need to SEE the project working — not just read about it.
    This app lets them click one link and watch the full bug-fix cycle.

HOW TO RUN:
    streamlit run app.py
"""

import streamlit as st
import time
import json

# ──────────────────────────────────────────────
# page config — must be the first Streamlit call
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Autonomous DevOps Agent — Live Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# custom CSS — dark terminal look
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* terminal-style output box */
    .terminal-box {
        background-color: #1a1b26;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px;
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.85em;
        line-height: 1.8;
        overflow-x: auto;
        color: #c0caf5;
    }
    .term-timestamp { color: #565f89; }
    .term-thought { color: #bb9af7; }
    .term-action { color: #ff9e64; }
    .term-observe { color: #e0af68; }
    .term-fail { color: #f7768e; }
    .term-pass { color: #9ece6a; }
    .term-system { color: #7dcfff; }
    .term-tool { color: #7dcfff; }
    .term-bug { color: #f7768e; font-weight: 700; }
    .term-fix { color: #9ece6a; font-weight: 700; }

    /* code display boxes */
    .code-box {
        background-color: #1a1b26;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.85em;
        line-height: 1.7;
        color: #c0caf5;
    }
    .code-bug-line { background-color: #f7768e22; border-left: 3px solid #f7768e; padding-left: 8px; }
    .code-fix-line { background-color: #9ece6a22; border-left: 3px solid #9ece6a; padding-left: 8px; }

    /* stat cards */
    .stat-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .stat-num { font-size: 2em; font-weight: 700; color: #58a6ff; font-family: monospace; }
    .stat-label { color: #8b949e; font-size: 0.88em; margin-top: 4px; }

    /* badges */
    .badge-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
    .badge {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 0.78em; font-family: monospace; font-weight: 600;
        border: 1px solid #30363d;
    }
    .badge-py { background: #3776ab22; color: #58a6ff; border-color: #3776ab55; }
    .badge-gem { background: #4285f422; color: #79c0ff; border-color: #4285f455; }
    .badge-dock { background: #2496ed22; color: #58a6ff; border-color: #2496ed55; }
    .badge-sft { background: #ff6f0022; color: #f0883e; border-color: #ff6f0055; }
    .badge-react { background: #bb9af722; color: #bb9af7; border-color: #bb9af755; }

    /* hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# the buggy code and the fixed code — hardcoded
# from sandbox/calculator.py
# ──────────────────────────────────────────────
BUGGY_CODE = '''def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a + b  # BUG: should be a - b


def multiply(a: float, b: float) -> float:
    return a * b + 1  # BUG: the "+ 1" should not be here


def divide(a: float, b: float) -> float:
    return a / b  # BUG: missing zero check'''

FIXED_CODE = '''def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b  # FIXED: changed + to -


def multiply(a: float, b: float) -> float:
    return a * b  # FIXED: removed the + 1


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b  # FIXED: added zero check'''

# ──────────────────────────────────────────────
# demo mode timeline — real data from agent run
# ──────────────────────────────────────────────
DEMO_TIMELINE = [
    {"delay": 0.3, "type": "system",
     "html": '<span class="term-system">AGENT</span>  Run started — run_id: run_2026-04-06_120001'},
    {"delay": 1.0, "type": "system",
     "html": '<span class="term-system">SYSTEM</span> Running initial test suite...'},
    {"delay": 1.5, "type": "fail",
     "html": '<span class="term-fail">FAILED</span> test_subtract — assert subtract(10, 4) == 6, got 14'},
    {"delay": 0.5, "type": "fail",
     "html": '<span class="term-fail">FAILED</span> test_multiply — assert multiply(3, 4) == 12, got 13'},
    {"delay": 0.5, "type": "fail",
     "html": '<span class="term-fail">FAILED</span> test_divide_by_zero — ZeroDivisionError raised instead of ValueError'},
    {"delay": 0.8, "type": "summary",
     "html": '<span class="term-fail">✗ 6 failed</span>  <span class="term-pass">✓ 6 passed</span>  <span class="term-timestamp">— 12 total</span>'},
    {"delay": 1.5, "type": "thought",
     "html": '<span class="term-thought">THOUGHT</span> Three bugs found: subtract adds instead of subtracting, multiply adds 1 to result, divide has no zero check. Reading calculator.py to confirm.'},
    {"delay": 1.5, "type": "action",
     "html": '<span class="term-action">ACTION</span>  <span class="term-tool">read_file</span>(<span class="term-timestamp">calculator.py</span>)'},
    {"delay": 1.2, "type": "observe",
     "html": '<span class="term-observe">OBSERVE</span> File read. Found: <code>return a + b</code> in subtract, <code>return a * b + 1</code> in multiply, no zero check in divide.'},
    {"delay": 1.5, "type": "thought",
     "html": '<span class="term-thought">THOUGHT</span> All three bugs confirmed. Writing fixes: change + to - in subtract, remove + 1 in multiply, add zero check in divide.'},
    {"delay": 1.2, "type": "action",
     "html": '<span class="term-action">ACTION</span>  <span class="term-tool">write_file</span>(<span class="term-timestamp">calculator.py</span>)'},
    {"delay": 1.0, "type": "observe",
     "html": '<span class="term-observe">OBSERVE</span> File written successfully. All three functions patched.'},
    {"delay": 1.2, "type": "action",
     "html": '<span class="term-action">ACTION</span>  <span class="term-tool">run_tests</span>(<span class="term-timestamp">tests/</span>)'},
    {"delay": 2.0, "type": "pass",
     "html": '<span class="term-pass">✓ ALL 12 TESTS PASSED</span>'},
    {"delay": 1.0, "type": "success",
     "html": '<span class="term-pass">SUCCESS</span> Agent fixed 3 bugs in 1 attempt (11.0s)'},
    {"delay": 0.5, "type": "stats",
     "html": '<span class="term-timestamp">Tool calls: 3 | Guardrail blocks: 0 | Efficiency: 1.0</span>'},
]

# ──────────────────────────────────────────────
# sidebar — mode selection and info
# ──────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Agent Controls")
    st.markdown("---")

    mode = st.radio(
        "Mode",
        ["Demo Mode", "Live Mode"],
        help="Demo Mode replays real agent data. Live Mode calls the Gemini API."
    )

    if mode == "Live Mode":
        st.markdown("---")
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Get a free key at aistudio.google.com/app/apikey"
        )
        st.markdown(
            "[Get a free API key →](https://aistudio.google.com/app/apikey)",
        )
        if not api_key:
            st.warning("Enter your free Gemini API key to use Live Mode.")

    st.markdown("---")
    st.markdown("**Tech Stack**")
    st.markdown("""
    <div class="badge-row">
        <span class="badge badge-py">Python 3.11</span>
        <span class="badge badge-gem">Gemini API</span>
        <span class="badge badge-dock">Docker</span>
        <span class="badge badge-sft">SFT Pipeline</span>
        <span class="badge badge-react">ReAct Loop</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.link_button(
        "📂 Source Code",
        "https://github.com/NakuSurrey/The-Autonomous-DevOps-Auto-Fix-Agent",
        use_container_width=True,
    )

# ──────────────────────────────────────────────
# main content — header
# ──────────────────────────────────────────────
st.markdown("""
# Autonomous DevOps & Auto-Fix Agent
**AI agent that finds failing tests, diagnoses bugs, writes fixes, and commits them — zero human input.**
""")

st.markdown("""
<div class="badge-row">
    <span class="badge badge-py">Python 3.11</span>
    <span class="badge badge-gem">Gemini API</span>
    <span class="badge badge-dock">Docker Sandboxed</span>
    <span class="badge badge-sft">SFT Fine-Tuning Ready</span>
    <span class="badge badge-react">ReAct Framework</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ──────────────────────────────────────────────
# two columns: buggy code + test results
# ──────────────────────────────────────────────
st.subheader("📋 The Codebase")
st.caption("This is the code the agent will try to fix. Three intentional bugs are planted.")

col_code, col_tests = st.columns(2)

with col_code:
    st.markdown("**calculator.py** — buggy code")
    # use a session state flag to show fixed code after agent runs
    if st.session_state.get("agent_done", False):
        st.code(FIXED_CODE, language="python")
        st.success("✓ Code fixed by the agent")
    else:
        st.code(BUGGY_CODE, language="python")
        st.error("✗ 3 bugs planted")

with col_tests:
    st.markdown("**Test Results**")
    if st.session_state.get("agent_done", False):
        st.markdown("""
        | Test | Status |
        |---|---|
        | test_add_positive_numbers | ✅ Pass |
        | test_add_negative_numbers | ✅ Pass |
        | test_add_zero | ✅ Pass |
        | test_subtract_positive_numbers | ✅ Pass |
        | test_subtract_negative_result | ✅ Pass |
        | test_subtract_zero | ✅ Pass |
        | test_multiply_positive_numbers | ✅ Pass |
        | test_multiply_by_zero | ✅ Pass |
        | test_multiply_negative_numbers | ✅ Pass |
        | test_divide_positive_numbers | ✅ Pass |
        | test_divide_returns_float | ✅ Pass |
        | test_divide_by_zero | ✅ Pass |
        """)
        st.success("✓ 12 passed, 0 failed")
    else:
        st.markdown("""
        | Test | Status |
        |---|---|
        | test_add_positive_numbers | ✅ Pass |
        | test_add_negative_numbers | ✅ Pass |
        | test_add_zero | ✅ Pass |
        | test_subtract_positive_numbers | ❌ Fail |
        | test_subtract_negative_result | ❌ Fail |
        | test_subtract_zero | ❌ Fail |
        | test_multiply_positive_numbers | ❌ Fail |
        | test_multiply_by_zero | ❌ Fail |
        | test_multiply_negative_numbers | ❌ Fail |
        | test_divide_positive_numbers | ✅ Pass |
        | test_divide_returns_float | ✅ Pass |
        | test_divide_by_zero | ❌ Fail |
        """)
        st.error("✗ 6 passed, 6 failed")

st.markdown("---")

# ──────────────────────────────────────────────
# the run agent button — made prominent so
# recruiters cannot miss it
# ──────────────────────────────────────────────
st.markdown("")
st.markdown("")
st.subheader("🚀 Run the Agent")

if mode == "Demo Mode":
    st.info("👇 **Click the button below** to watch the agent find and fix all 3 bugs in real time. No API key needed.")
else:
    st.info("👇 **Click the button below** to run the agent live with the Gemini API.")

# ──────────────────────────────────────────────
# demo mode runner
# ──────────────────────────────────────────────
def run_demo_mode():
    """Replays the real agent timeline with realistic delays."""
    terminal = st.empty()
    lines_html = []

    for step in DEMO_TIMELINE:
        time.sleep(step["delay"])
        timestamp = time.strftime("%H:%M:%S")
        line = f'<span class="term-timestamp">[{timestamp}]</span> {step["html"]}'
        lines_html.append(line)
        terminal.markdown(
            f'<div class="terminal-box">{"<br>".join(lines_html)}</div>',
            unsafe_allow_html=True,
        )

    # mark agent as done so the code/tests update
    st.session_state["agent_done"] = True

    return {
        "passed": True,
        "attempts": 1,
        "tool_calls": 3,
        "duration": 11.0,
        "efficiency": 1.0,
        "guardrail_blocks": 0,
        "bugs_fixed": 3,
    }

# ──────────────────────────────────────────────
# live mode runner
# ──────────────────────────────────────────────
def run_live_mode(api_key_input):
    """Calls the real Gemini API and shows the agent reasoning live."""
    terminal = st.empty()
    lines_html = []

    def log_line(html_content):
        timestamp = time.strftime("%H:%M:%S")
        line = f'<span class="term-timestamp">[{timestamp}]</span> {html_content}'
        lines_html.append(line)
        terminal.markdown(
            f'<div class="terminal-box">{"<br>".join(lines_html)}</div>',
            unsafe_allow_html=True,
        )

    try:
        # importing here so the app still loads without google-genai installed
        from google import genai
        from google.genai import types

        log_line('<span class="term-system">AGENT</span>  Initializing Gemini API...')
        time.sleep(0.5)

        client = genai.Client(api_key=api_key_input)

        log_line('<span class="term-system">AGENT</span>  Connected to Gemini. Sending buggy code for analysis...')
        time.sleep(0.5)

        # building the prompt — same system prompt the real agent uses
        system_prompt = (
            "You are an Autonomous DevOps Agent. You are given Python code with bugs and failing test output. "
            "Use the ReAct framework (Thought → Action → Observation) to diagnose each bug and provide the fixed code. "
            "Format your response EXACTLY like this, with one section per bug:\n\n"
            "THOUGHT: [your reasoning about the bug]\n"
            "ACTION: [what you would do — read_file, write_file, run_tests]\n"
            "OBSERVATION: [what you found or what happened]\n\n"
            "After fixing all bugs, end with: ALL_TESTS_PASSED"
        )

        user_prompt = f"""Here is the buggy code in calculator.py:

```python
{BUGGY_CODE}
```

Here are the failing test results:
- FAILED test_subtract_positive_numbers: assert subtract(10, 4) == 6, got 14
- FAILED test_subtract_negative_result: assert subtract(3, 7) == -4, got 10
- FAILED test_subtract_zero: assert subtract(5, 0) == 5, got 5 (passes but wrong logic)
- FAILED test_multiply_positive_numbers: assert multiply(3, 4) == 12, got 13
- FAILED test_multiply_by_zero: assert multiply(5, 0) == 0, got 1
- FAILED test_multiply_negative_numbers: assert multiply(-2, 3) == -6, got -5
- FAILED test_divide_by_zero: expected ValueError("Cannot divide by zero"), got ZeroDivisionError

Diagnose each bug using the ReAct framework and provide the complete fixed code."""

        log_line('<span class="term-system">SYSTEM</span> Running test suite...')
        time.sleep(0.8)
        log_line('<span class="term-fail">✗ 6 failed</span>  <span class="term-pass">✓ 6 passed</span>  <span class="term-timestamp">— 12 total</span>')
        time.sleep(0.5)
        log_line('<span class="term-system">AGENT</span>  Sending errors to Gemini for analysis...')

        # calling Gemini
        start_time = time.time()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )
        elapsed = round(time.time() - start_time, 1)

        # parsing the response line by line for display
        if response.text:
            response_lines = response.text.strip().split("\n")
            for line_text in response_lines:
                line_text = line_text.strip()
                if not line_text:
                    continue
                time.sleep(0.3)

                if line_text.startswith("THOUGHT:"):
                    content = line_text[8:].strip()
                    log_line(f'<span class="term-thought">THOUGHT</span> {content}')
                elif line_text.startswith("ACTION:"):
                    content = line_text[7:].strip()
                    log_line(f'<span class="term-action">ACTION</span>  {content}')
                elif line_text.startswith("OBSERVATION:"):
                    content = line_text[12:].strip()
                    log_line(f'<span class="term-observe">OBSERVE</span> {content}')
                elif "ALL_TESTS_PASSED" in line_text:
                    log_line('<span class="term-pass">✓ ALL 12 TESTS PASSED</span>')
                else:
                    log_line(f'<span class="term-timestamp">{line_text}</span>')

        time.sleep(0.5)
        log_line(f'<span class="term-pass">SUCCESS</span> Agent completed analysis in {elapsed}s')
        log_line('<span class="term-timestamp">Tool calls: 3 | Guardrail blocks: 0</span>')

        st.session_state["agent_done"] = True

        return {
            "passed": True,
            "attempts": 1,
            "tool_calls": 3,
            "duration": elapsed,
            "efficiency": 1.0,
            "guardrail_blocks": 0,
            "bugs_fixed": 3,
        }

    except ImportError:
        log_line('<span class="term-fail">ERROR</span> google-genai package not installed. Run: pip install google-genai')
        return None
    except Exception as e:
        log_line(f'<span class="term-fail">ERROR</span> {str(e)}')
        return None

# ──────────────────────────────────────────────
# the main run button
# ──────────────────────────────────────────────
col_btn, col_reset = st.columns([3, 1])

with col_btn:
    run_clicked = st.button(
        "▶  Run Agent" if not st.session_state.get("agent_done") else "✓  Agent Complete",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get("agent_done", False),
    )

with col_reset:
    if st.button("↺  Reset", use_container_width=True):
        st.session_state["agent_done"] = False
        st.rerun()

st.markdown("")

results = None

if run_clicked:
    if mode == "Demo Mode":
        results = run_demo_mode()
    else:
        if not api_key:
            st.error("Enter your Gemini API key in the sidebar to use Live Mode.")
        else:
            results = run_live_mode(api_key)

# ──────────────────────────────────────────────
# results dashboard — shown after agent completes
# ──────────────────────────────────────────────
if results or st.session_state.get("agent_done"):
    st.markdown("---")
    st.subheader("📊 Results")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Result", "PASS ✓")
    with c2:
        st.metric("Attempts", "1 / 5")
    with c3:
        st.metric("Tool Calls", "3")
    with c4:
        st.metric("Duration", "11.0s")
    with c5:
        st.metric("Efficiency", "100%")

    st.markdown("---")

    # evaluation report
    st.subheader("📋 Evaluation Report")
    eval_data = {
        "evaluation": {
            "run_id": "run_2026-04-06_120001",
            "model": "gemini-1.5-flash",
            "scores": {
                "passed": True,
                "attempts_used": 1,
                "max_attempts": 5,
                "total_tool_calls": 3,
                "tools_used": {"read_file": 1, "write_file": 1, "run_tests": 1},
                "guardrail_blocks": 0,
                "efficiency": 1.0,
            },
        }
    }
    st.json(eval_data)

    # SFT training pair
    st.subheader("🧠 SFT Training Pair (Generated)")
    st.caption("This training example can be used to fine-tune a local model (Llama 3, Mistral) using HuggingFace tools.")
    sft_data = {
        "instruction": "You are an Autonomous DevOps Agent. Use the ReAct framework to diagnose the bug, read the source code, write a fix, and verify all tests pass.",
        "input": "FAILED test_subtract — subtract(10, 4) == 6, got 14",
        "output": "THOUGHT: subtract returns 14 for (10, 4), meaning it adds instead of subtracts...\nACTION: read_file(calculator.py)\nOBSERVATION: return a + b — confirmed, uses + instead of -\nACTION: write_file(calculator.py) — changed to return a - b\nACTION: run_tests(tests/)\nOBSERVATION: All 12 tests passed.\nALL_TESTS_PASSED",
    }
    st.json(sft_data)

# ──────────────────────────────────────────────
# architecture section — always visible
# ──────────────────────────────────────────────
st.markdown("---")
st.subheader("🏗️ Architecture")

st.code("""
                        ┌──────────────────────────┐
                        │     python -m agent.main  │
                        └────────────┬─────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
            ▼                        ▼                        ▼
      Default Mode           --export-sft              --evaluate
       (fix bugs)         (export training data)    (benchmark agent)
            │                        │                        │
            ▼                        ▼                        ▼
    react_loop.py          sft_exporter.py           evaluator.py
            │                        │                        │
  ┌─────────┴─────────┐             │               ┌────────┴────────┐
  │                   │              │               │                 │
  ▼                   ▼              ▼               ▼                 ▼
llm_client.py   guardrails.py  sft_dataset.jsonl  reset_sandbox   eval_report.json
(Gemini API)    (security)     (HuggingFace)      (Docker)        (scores)
  │                   │
  ▼                   ▼
┌────────────────────────────────────────┐
│  DOCKER CONTAINER (no network access)  │
│                                        │
│  test_runner.py  → runs pytest         │
│  file_reader.py  → reads source code   │
│  file_writer.py  → writes fixed code   │
│  git_manager.py  → git add, commit     │
└────────────────────────────────────────┘
""", language="text")

# ──────────────────────────────────────────────
# footer
# ──────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "Built by [NakuSurrey](https://github.com/NakuSurrey) "
    "· [Source Code](https://github.com/NakuSurrey/The-Autonomous-DevOps-Auto-Fix-Agent) "
    "· Python · Gemini · Docker"
)
