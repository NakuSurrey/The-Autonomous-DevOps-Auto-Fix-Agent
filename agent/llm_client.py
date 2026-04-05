"""
llm_client.py — Talks to the Google Gemini API

WHAT THIS FILE DOES:
    Creates and manages the connection to the Gemini API.
    Sends prompts to the LLM and receives responses.
    Handles the tool-calling (function calling) protocol.

WHY IT EXISTS:
    The agent needs an LLM to reason about errors and generate fixes.
    This file wraps all Gemini API communication in one place.
    If we ever swap Gemini for a different LLM, we only change this file.

WHERE IT SITS IN THE CODEBASE:
    agent/llm_client.py
    ├── Reads from: agent/config.py (API key, model name)
    ├── Reads from: agent/prompt_templates.py (system prompt, tool declarations)
    ├── Used by: agent/react_loop.py (sends messages, receives tool calls)
    └── Depends on: google-genai package (the NEW official Google Gemini SDK)

HOW IT WORKS:
    Step 1 → Initialize: Create a Gemini Client with the API key
    Step 2 → Start chat: Create a conversation with system prompt + tools
    Step 3 → Send message: Send a user message, get back either text or a tool call
    Step 4 → Send tool result: After executing a tool, send its result back to continue
"""

from google import genai
from google.genai import types
from agent.config import GEMINI_API_KEY, GEMINI_MODEL
from agent.prompt_templates import SYSTEM_PROMPT, AGENT_TOOLS


class LLMClient:
    """
    Manages the conversation with the Gemini API.

    HOW A CONVERSATION WORKS:
        A "chat" in Gemini is a back-and-forth sequence of messages.
        Each message has a role:
          - "user"  = messages we send TO the LLM
          - "model" = messages the LLM sends back TO us

        The chat keeps history. So when the LLM responds, it remembers
        everything that was said before. This is how the ReAct loop works:
        the LLM can see all previous Thoughts, Actions, and Observations.
    """

    def __init__(self):
        """
        Sets up the Gemini client.

        WHAT HAPPENS HERE:
            Step 1 → Create a genai.Client with our API key
            Step 2 → Store the model name and config for later use
            Step 3 → chat is set to None (created when start_chat() is called)
        """
        # --------------------------------------------------
        # Step 1: Create the client
        # --------------------------------------------------
        # genai.Client is the main entry point for the new SDK.
        # We pass the API key here. All subsequent API calls
        # go through this client.
        # --------------------------------------------------
        self.client = genai.Client(api_key=GEMINI_API_KEY)

        # --------------------------------------------------
        # Step 2: Store model name and build the config
        # --------------------------------------------------
        # GenerateContentConfig holds:
        #   - system_instruction: the system prompt
        #   - tools: the tool declarations (what functions LLM can call)
        #
        # This config is passed when creating the chat session.
        # --------------------------------------------------
        self.model_name = GEMINI_MODEL

        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[AGENT_TOOLS],
        )

        # Chat session — created when start_chat() is called
        self.chat = None

    def start_chat(self) -> None:
        """
        Starts a new conversation with the LLM.

        WHAT THIS DOES:
            Creates a "chat session" — a stateful conversation
            that remembers all previous messages. Every subsequent
            call to send_message() adds to this conversation.

        WHY WE NEED IT:
            The ReAct loop requires context. When the LLM decides
            to read a file in step 3, it needs to remember the
            error output from step 1. The chat session keeps all
            of this history automatically.
        """
        self.chat = self.client.chats.create(
            model=self.model_name,
            config=self.config,
        )

    def send_message(self, message: str) -> dict:
        """
        Sends a message to the LLM and returns its response.

        Parameters:
            message (str): The message to send (user role).

        Returns:
            dict with:
                "type" (str): Either "text" or "function_call"
                "content" (str or dict):
                    If type="text": the LLM's text response
                    If type="function_call": dict with "name" and "args"

        HOW IT WORKS:
            Step 1 → Send the message to Gemini via the chat session
            Step 2 → Gemini responds with either:
                     a) Plain text (its reasoning/thought)
                     b) A function call (it wants to use a tool)
            Step 3 → We detect which type it is and return it
        """
        if self.chat is None:
            raise RuntimeError(
                "Chat not started. Call start_chat() first."
            )

        # --------------------------------------------------
        # Step 1: Send the message
        # --------------------------------------------------
        response = self.chat.send_message(message)

        # --------------------------------------------------
        # Step 2: Parse the response
        # --------------------------------------------------
        return self._parse_response(response)

    def send_tool_result(self, function_name: str, result: str) -> dict:
        """
        Sends the result of a tool call back to the LLM.

        WHAT THIS DOES:
            After we execute a tool (e.g., run_tests), we need to
            tell the LLM what happened. This method sends the tool's
            output back as a "function response" so the LLM can
            continue its reasoning.

        Parameters:
            function_name (str): The name of the tool that was called.
            result (str): The output from the tool.

        Returns:
            dict: Same format as send_message() — either text or function_call.

        HOW THE GEMINI FUNCTION CALLING PROTOCOL WORKS:
            Step 1 → We send a user message
            Step 2 → Gemini responds with a function_call
            Step 3 → We execute the function
            Step 4 → We send the result back using this method
            Step 5 → Gemini reads the result and either:
                     a) Responds with text (its next thought)
                     b) Makes another function_call (needs more info)
        """
        # --------------------------------------------------
        # Build the function response part
        # --------------------------------------------------
        # Gemini expects the tool result in a specific format:
        # A Part created with from_function_response containing:
        #   - name: which function this is the result for
        #   - response: a dict with the result data
        # --------------------------------------------------
        function_response_part = types.Part.from_function_response(
            name=function_name,
            response={"result": result},
        )

        # Send the function response back through the chat
        response = self.chat.send_message(function_response_part)

        # Parse the response the same way as send_message
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        """
        Parses a Gemini response into our standard format.

        Gemini's response has "candidates". Each candidate has
        "content" with "parts". Each part is either:
          - A text part (the LLM wrote text)
          - A function_call part (the LLM wants to call a tool)

        We check the FIRST part to determine the response type.

        Parameters:
            response: The raw response from Gemini API.

        Returns:
            dict with "type" and "content" keys.
        """
        # Get the first part from the response
        part = response.candidates[0].content.parts[0]

        # --------------------------------------------------
        # Check if it is a function call
        # --------------------------------------------------
        # If the LLM wants to call a tool, the part has a
        # "function_call" attribute with:
        #   - .name = the tool name (e.g., "run_tests")
        #   - .args = the arguments (e.g., {"test_path": "tests/"})
        # --------------------------------------------------
        if part.function_call and part.function_call.name:
            return {
                "type": "function_call",
                "content": {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args) if part.function_call.args else {},
                },
            }

        # --------------------------------------------------
        # It is a text response
        # --------------------------------------------------
        return {
            "type": "text",
            "content": part.text if part.text else str(part),
        }
