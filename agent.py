"""
Conversation manager and agent logic for Bookly support agent.
"""

import json
from datetime import datetime
from openai import OpenAI
from tools import TOOLS, execute_tool


def load_agent_config():
    """Load the agent configuration from agents.md."""
    with open('agents.md', 'r') as f:
        return f.read()


def build_system_prompt():
    """Build the system prompt including agent config and current date."""
    config = load_agent_config()
    return f"""{config}

## Additional Instructions
- Today's date is {datetime.now().strftime('%Y-%m-%d')}
- Use the tools provided to look up real data
- Never make up order information
- If a tool returns an error, tell the customer and offer alternatives
"""


class ConversationManager:
    """Manages conversations with customers using OpenAI."""

    def __init__(self):
        self.client = OpenAI()
        self.conversations = {}  # session_id -> messages list

    def get_or_create_conversation(self, session_id):
        """Get existing conversation or create a new one."""
        if session_id not in self.conversations:
            self.conversations[session_id] = [
                {"role": "system", "content": build_system_prompt()}
            ]
        return self.conversations[session_id]

    def chat(self, session_id, user_message):
        """Process a user message and return the agent's response."""
        messages = self.get_or_create_conversation(session_id)
        messages.append({"role": "user", "content": user_message})

        # Call OpenAI with tools
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # Handle tool calls if present
        if assistant_message.tool_calls:
            return self._handle_tool_calls(session_id, assistant_message)
        else:
            messages.append({"role": "assistant", "content": assistant_message.content})
            return assistant_message.content

    def _handle_tool_calls(self, session_id, assistant_message):
        """Execute tool calls and get final response."""
        messages = self.conversations[session_id]

        # Add assistant message with tool calls
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })

        # Execute each tool and add results
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            result = execute_tool(tool_name, arguments)

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps(result)
            })

        # Get final response after tool execution
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS
        )

        final_message = response.choices[0].message

        # Handle nested tool calls if needed
        if final_message.tool_calls:
            return self._handle_tool_calls(session_id, final_message)

        messages.append({"role": "assistant", "content": final_message.content})
        return final_message.content

    def reset_conversation(self, session_id):
        """Reset a conversation to start fresh."""
        if session_id in self.conversations:
            del self.conversations[session_id]
