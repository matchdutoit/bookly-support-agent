"""Flask backend for Bookly customer support agent and Matchagon admin portal."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from agent import ConversationManager
from tool_registry import ToolRegistryManager

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

conversation_manager = ConversationManager()
tool_registry = ToolRegistryManager("tools.py")
agent_config_file = Path("agents.md")


def _parse_optional_int(raw_value: str | None) -> int | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"Invalid integer value: {raw_value}") from error


def _parse_days_filter(raw_value: str | None) -> int | None:
    if raw_value is None or raw_value == "":
        return 30
    if raw_value.lower() == "none":
        return None
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"Invalid days value: {raw_value}") from error


@app.route("/")
def index():
    """Serve the customer-facing chat interface."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/admin")
def admin():
    """Serve Matchagon administrator portal."""
    return render_template("admin.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat messages from the frontend."""
    data = request.json or {}
    user_message = data.get("message", "")

    session_id = session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        session["session_id"] = session_id

    try:
        response = conversation_manager.chat(session_id, user_message)
        return jsonify({"success": True, "response": response})
    except Exception as error:  # pragma: no cover - runtime guard
        return jsonify({"success": False, "error": str(error)}), 500


@app.route("/reset", methods=["POST"])
def reset():
    """Reset the conversation to start fresh."""
    session_id = session.get("session_id")
    if session_id:
        conversation_manager.reset_conversation(session_id)
    session["session_id"] = str(uuid.uuid4())
    return jsonify({"success": True})


@app.route("/api/admin/metrics", methods=["GET"])
def admin_metrics():
    """Return high-level performance metrics for dashboard tiles/charts."""
    days = int(request.args.get("days", 30))
    metrics = conversation_manager.audit_store.get_metrics(days=days)
    return jsonify({"success": True, "metrics": metrics})


@app.route("/api/admin/conversations", methods=["GET"])
def admin_conversations():
    """Return filtered conversation list for the past N days."""
    try:
        days = _parse_days_filter(request.args.get("days", "30"))
        topic = request.args.get("topic") or None
        status = request.args.get("status") or None
        sort = request.args.get("sort", "newest").lower()
        min_user_messages = _parse_optional_int(request.args.get("min_user_messages"))
        max_user_messages = _parse_optional_int(request.args.get("max_user_messages"))
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400

    if topic == "all":
        topic = None
    if status == "all":
        status = None

    sort_map = {
        "newest": "desc",
        "oldest": "asc",
        "desc": "desc",
        "asc": "asc",
    }
    if sort not in sort_map:
        return jsonify({"success": False, "error": f"Invalid sort value: {sort}"}), 400

    conversations = conversation_manager.audit_store.list_conversations(
        days=days,
        topic=topic,
        disposition=status,
        min_user_messages=min_user_messages,
        max_user_messages=max_user_messages,
        sort_order=sort_map[sort],
    )
    return jsonify({"success": True, "conversations": conversations})


@app.route("/api/admin/conversations/<int:conversation_id>", methods=["GET"])
def admin_conversation_detail(conversation_id: int):
    """Return a full conversation transcript for drawer view."""
    conversation = conversation_manager.audit_store.get_conversation(conversation_id)
    if not conversation:
        return jsonify({"success": False, "error": "Conversation not found"}), 404
    return jsonify({"success": True, "conversation": conversation})


@app.route("/api/admin/build/aop", methods=["GET", "PUT"])
def admin_build_aop():
    """Read or update agents.md content."""
    if request.method == "GET":
        return jsonify({"success": True, "content": agent_config_file.read_text(encoding="utf-8")})

    data = request.json or {}
    content = data.get("content")
    if not isinstance(content, str):
        return jsonify({"success": False, "error": "Expected 'content' as string"}), 400

    agent_config_file.write_text(content, encoding="utf-8")
    return jsonify({"success": True})


@app.route("/api/admin/tools", methods=["GET", "POST"])
def admin_tools():
    """List existing tools or add a new tool."""
    if request.method == "GET":
        return jsonify({"success": True, "tools": tool_registry.list_tools()})

    data = request.json or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    code = data.get("code") or ""
    parameters = data.get("parameters", {})

    if isinstance(parameters, str):
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Parameters must be valid JSON"}), 400

    if not name or not code:
        return jsonify({"success": False, "error": "Tool name and code are required"}), 400

    try:
        tool_registry.add_tool(
            name=name,
            description=description,
            parameters=parameters,
            code=code,
        )
        return jsonify({"success": True})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/admin/tools/<tool_name>", methods=["PUT"])
def admin_update_tool(tool_name: str):
    """Update source code for an existing tool function."""
    data = request.json or {}
    code = data.get("code") or ""

    if not code:
        return jsonify({"success": False, "error": "Tool code is required"}), 400

    try:
        tool_registry.update_tool_code(tool_name, code)
        return jsonify({"success": True})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
