"""Conversation manager and agent logic for Bookly support agent."""

from __future__ import annotations

import importlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

import tools as tools_module
from conversation_audit import ConversationAuditStore


def load_agent_config() -> str:
    """Load the agent configuration from agents.md."""
    with open("agents.md", "r", encoding="utf-8") as file:
        return file.read()


def build_system_prompt() -> str:
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

    def __init__(self, audit_store: ConversationAuditStore | None = None):
        self.client = OpenAI()
        self.audit_store = audit_store or ConversationAuditStore()
        self.conversations: dict[str, list[dict[str, Any]]] = {}
        self.tools_module = tools_module
        self.tools_file = Path("tools.py")
        self.tools_mtime = self._get_tools_mtime()

    def _get_tools_mtime(self) -> float:
        if self.tools_file.exists():
            return os.path.getmtime(self.tools_file)
        return 0

    def _refresh_tools_if_updated(self) -> None:
        current_mtime = self._get_tools_mtime()
        if current_mtime > self.tools_mtime:
            self.tools_module = importlib.reload(self.tools_module)
            self.tools_mtime = current_mtime

    def get_or_create_conversation(self, session_id: str) -> list[dict[str, Any]]:
        """Get existing conversation or create a new one."""
        if session_id not in self.conversations:
            self.conversations[session_id] = [{"role": "system", "content": build_system_prompt()}]
            self.audit_store.ensure_conversation(session_id)
        return self.conversations[session_id]

    def _log_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.audit_store.log_message(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

    def _sync_classification(self, session_id: str) -> None:
        messages = self.conversations.get(session_id, [])
        self.audit_store.sync_classification(session_id, messages)

    def chat(self, session_id: str, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self._refresh_tools_if_updated()

        messages = self.get_or_create_conversation(session_id)
        messages.append({"role": "user", "content": user_message})
        self._log_message(session_id, "user", user_message)

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=self.tools_module.TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            return self._handle_tool_calls(session_id, assistant_message)

        messages.append({"role": "assistant", "content": assistant_message.content})
        self._log_message(session_id, "assistant", assistant_message.content)
        self._sync_classification(session_id)
        return assistant_message.content or ""

    def _handle_tool_calls(self, session_id: str, assistant_message: Any) -> str:
        """Execute tool calls and get final response."""
        self._refresh_tools_if_updated()
        messages = self.conversations[session_id]

        tool_call_payload = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in assistant_message.tool_calls
        ]

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": tool_call_payload,
            }
        )
        self._log_message(
            session_id,
            "assistant",
            assistant_message.content,
            metadata={"tool_calls": tool_call_payload},
        )

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            result = self.tools_module.execute_tool(tool_name, arguments)
            serialized_result = json.dumps(result)

            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": serialized_result,
                }
            )
            self._log_message(
                session_id,
                "tool",
                serialized_result,
                metadata={"tool_name": tool_name, "arguments": arguments},
            )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=self.tools_module.TOOLS,
        )

        final_message = response.choices[0].message

        if final_message.tool_calls:
            return self._handle_tool_calls(session_id, final_message)

        messages.append({"role": "assistant", "content": final_message.content})
        self._log_message(session_id, "assistant", final_message.content)
        self._sync_classification(session_id)
        return final_message.content or ""

    def reset_conversation(self, session_id: str) -> None:
        """Reset a conversation to start fresh."""
        if session_id in self.conversations:
            self._sync_classification(session_id)
            del self.conversations[session_id]
