"""Persistent conversation logging and analytics for Matchagon admin views."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openai import OpenAI


TOPIC_LABELS = {
    "order_status": "Order Status",
    "returns_refunds": "Returns & Refunds",
    "order_changes": "Order Changes",
    "general_inquiry": "General Inquiry",
}

DISPOSITION_LABELS = {
    "open": "Open",
    "resolved": "Resolved",
    "escalated": "Escalated",
}


def _utc_now_iso() -> str:
    """UTC timestamp in ISO-8601 with Z suffix."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalize_topic(topic: str) -> str:
    if topic in TOPIC_LABELS:
        return topic
    return "general_inquiry"


def _normalize_disposition(disposition: str) -> str:
    if disposition in DISPOSITION_LABELS:
        return disposition
    return "open"


class ConversationAuditStore:
    """SQLite-backed store for audited conversations and analytics."""

    def __init__(self, db_path: str = "matchagon.db", classifier_model: str | None = None):
        self.db_path = Path(db_path)
        self.classifier_model = classifier_model or os.getenv("MATCHAGON_CLASSIFIER_MODEL", "gpt-4o-mini")
        self._classifier_client: OpenAI | None = None
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT 'general_inquiry',
                    disposition TEXT NOT NULL DEFAULT 'open',
                    user_message_count INTEGER NOT NULL DEFAULT 0,
                    total_message_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )

    def ensure_conversation(self, session_id: str) -> int:
        """Create conversation row if needed and return its id."""
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing:
                return int(existing["id"])

            timestamp = _utc_now_iso()
            cursor = connection.execute(
                """
                INSERT INTO conversations (
                    session_id, started_at, updated_at, topic, disposition,
                    user_message_count, total_message_count
                ) VALUES (?, ?, ?, 'general_inquiry', 'open', 0, 0)
                """,
                (session_id, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

    def log_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a message for audit and update counters."""
        if role == "system":
            return

        conversation_id = self.ensure_conversation(session_id)
        timestamp = _utc_now_iso()
        metadata_json = json.dumps(metadata) if metadata else None

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, timestamp, metadata_json),
            )
            connection.execute(
                """
                UPDATE conversations
                SET
                    updated_at = ?,
                    total_message_count = total_message_count + 1,
                    user_message_count = user_message_count + ?
                WHERE id = ?
                """,
                (timestamp, 1 if role == "user" else 0, conversation_id),
            )

    def sync_classification(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Recompute conversation-level labels from current in-memory transcript."""
        conversation_id = self.ensure_conversation(session_id)
        non_system_messages = [m for m in messages if m.get("role") != "system"]
        user_message_count = sum(1 for m in non_system_messages if m.get("role") == "user")

        topic, disposition = self._infer_labels(messages)

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET
                    updated_at = ?,
                    topic = ?,
                    disposition = ?,
                    user_message_count = ?,
                    total_message_count = ?
                WHERE id = ?
                """,
                (
                    _utc_now_iso(),
                    _normalize_topic(topic),
                    _normalize_disposition(disposition),
                    user_message_count,
                    len(non_system_messages),
                    conversation_id,
                ),
            )

    def _get_classifier_client(self) -> OpenAI | None:
        if self._classifier_client is not None:
            return self._classifier_client

        if not os.getenv("OPENAI_API_KEY"):
            return None

        self._classifier_client = OpenAI()
        return self._classifier_client

    def _infer_labels(self, messages: list[dict[str, Any]]) -> tuple[str, str]:
        llm_labels = self._infer_labels_with_llm(messages)
        if llm_labels is not None:
            return llm_labels

        return (
            self._infer_topic_fallback(messages),
            self._infer_disposition_fallback(messages),
        )

    def _infer_labels_with_llm(self, messages: list[dict[str, Any]]) -> tuple[str, str] | None:
        client = self._get_classifier_client()
        if client is None:
            return None

        transcript = self._build_classification_transcript(messages)
        if not transcript:
            return None

        system_prompt = (
            "You classify customer support conversations.\n"
            "Return strict JSON with keys: topic, disposition.\n"
            "Allowed topic values: order_status, returns_refunds, order_changes, general_inquiry.\n"
            "Allowed disposition values: open, resolved, escalated.\n"
            "Rules:\n"
            "- Use 'escalated' if the assistant handed off to a human/supervisor or said it cannot complete.\n"
            "- Use 'resolved' if the conversation outcome appears completed or answer delivered.\n"
            "- Otherwise use 'open'.\n"
            "Do not return any text outside JSON."
        )

        try:
            response = client.chat.completions.create(
                model=self.classifier_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
            payload = json.loads(raw_content)

            if not isinstance(payload, dict):
                return None

            topic = _normalize_topic(str(payload.get("topic", "")).strip())
            disposition = _normalize_disposition(str(payload.get("disposition", "")).strip())
            return topic, disposition
        except Exception:
            return None

    def _build_classification_transcript(self, messages: list[dict[str, Any]]) -> str:
        transcript_lines = []

        # Keep context bounded to reduce token usage and latency.
        for message in messages[-30:]:
            role = message.get("role")
            if role == "system":
                continue

            content = self._truncate_text(message.get("content") or "", max_chars=500)
            if role == "assistant" and message.get("tool_calls"):
                tool_names = []
                for tool_call in message["tool_calls"]:
                    function_data = tool_call.get("function", {})
                    tool_name = function_data.get("name")
                    if tool_name:
                        tool_names.append(tool_name)

                if tool_names:
                    content = f"{content} [tool_calls={','.join(tool_names)}]".strip()

            transcript_lines.append(f"{role}: {content}")

        return "\n".join(transcript_lines)

    def _truncate_text(self, content: str, *, max_chars: int) -> str:
        if len(content) <= max_chars:
            return content
        return f"{content[:max_chars]}..."

    def list_conversations(
        self,
        *,
        days: int = 30,
        topic: str | None = None,
        min_user_messages: int | None = None,
        max_user_messages: int | None = None,
    ) -> list[dict[str, Any]]:
        """List conversations with optional topic and length filters."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.replace(microsecond=0).isoformat() + "Z"

        where_parts = ["c.updated_at >= ?"]
        params: list[Any] = [cutoff_iso]

        if topic:
            where_parts.append("c.topic = ?")
            params.append(_normalize_topic(topic))

        if min_user_messages is not None:
            where_parts.append("c.user_message_count >= ?")
            params.append(min_user_messages)

        if max_user_messages is not None:
            where_parts.append("c.user_message_count <= ?")
            params.append(max_user_messages)

        where_clause = " AND ".join(where_parts)

        query = f"""
            SELECT
                c.id,
                c.session_id,
                c.started_at,
                c.updated_at,
                c.topic,
                c.disposition,
                c.user_message_count,
                c.total_message_count,
                (
                    SELECT m.content
                    FROM messages m
                    WHERE m.conversation_id = c.id AND m.role = 'user'
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_user_message
            FROM conversations c
            WHERE {where_clause}
            ORDER BY c.updated_at DESC
        """

        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        conversations: list[dict[str, Any]] = []
        for row in rows:
            conversations.append(
                {
                    "id": int(row["id"]),
                    "session_id": row["session_id"],
                    "started_at": row["started_at"],
                    "updated_at": row["updated_at"],
                    "topic": row["topic"],
                    "topic_label": TOPIC_LABELS.get(row["topic"], row["topic"]),
                    "disposition": row["disposition"],
                    "disposition_label": DISPOSITION_LABELS.get(row["disposition"], row["disposition"]),
                    "user_message_count": int(row["user_message_count"]),
                    "total_message_count": int(row["total_message_count"]),
                    "last_user_message": row["last_user_message"] or "",
                }
            )
        return conversations

    def get_conversation(self, conversation_id: int) -> dict[str, Any] | None:
        """Get a conversation and full message transcript by id."""
        with self._connect() as connection:
            conversation = connection.execute(
                """
                SELECT id, session_id, started_at, updated_at, topic, disposition,
                       user_message_count, total_message_count
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

            if not conversation:
                return None

            message_rows = connection.execute(
                """
                SELECT id, role, content, created_at, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()

        messages = []
        for row in message_rows:
            metadata = None
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    metadata = {"raw": row["metadata"]}

            messages.append(
                {
                    "id": int(row["id"]),
                    "role": row["role"],
                    "content": row["content"] or "",
                    "created_at": row["created_at"],
                    "metadata": metadata,
                }
            )

        return {
            "id": int(conversation["id"]),
            "session_id": conversation["session_id"],
            "started_at": conversation["started_at"],
            "updated_at": conversation["updated_at"],
            "topic": conversation["topic"],
            "topic_label": TOPIC_LABELS.get(conversation["topic"], conversation["topic"]),
            "disposition": conversation["disposition"],
            "disposition_label": DISPOSITION_LABELS.get(conversation["disposition"], conversation["disposition"]),
            "user_message_count": int(conversation["user_message_count"]),
            "total_message_count": int(conversation["total_message_count"]),
            "messages": messages,
        }

    def get_topic_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        """Get topic counts for charting."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.replace(microsecond=0).isoformat() + "Z"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT topic, COUNT(*) AS count
                FROM conversations
                WHERE updated_at >= ?
                GROUP BY topic
                ORDER BY count DESC
                """,
                (cutoff_iso,),
            ).fetchall()

        return [
            {
                "topic": row["topic"],
                "topic_label": TOPIC_LABELS.get(row["topic"], row["topic"]),
                "count": int(row["count"]),
            }
            for row in rows
        ]

    def get_disposition_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        """Get disposition counts for charting."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.replace(microsecond=0).isoformat() + "Z"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT disposition, COUNT(*) AS count
                FROM conversations
                WHERE updated_at >= ?
                GROUP BY disposition
                ORDER BY count DESC
                """,
                (cutoff_iso,),
            ).fetchall()

        return [
            {
                "disposition": row["disposition"],
                "disposition_label": DISPOSITION_LABELS.get(row["disposition"], row["disposition"]),
                "count": int(row["count"]),
            }
            for row in rows
        ]

    def get_metrics(self, days: int = 30) -> dict[str, Any]:
        """Compute summary metrics for Home page tiles."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff.replace(microsecond=0).isoformat() + "Z"

        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_conversations,
                    SUM(CASE WHEN disposition = 'resolved' THEN 1 ELSE 0 END) AS resolved_conversations,
                    AVG(user_message_count) AS avg_user_messages
                FROM conversations
                WHERE updated_at >= ?
                """,
                (cutoff_iso,),
            ).fetchone()

            top_topic = connection.execute(
                """
                SELECT topic, COUNT(*) AS count
                FROM conversations
                WHERE updated_at >= ?
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 1
                """,
                (cutoff_iso,),
            ).fetchone()

        total = int(totals["total_conversations"] or 0)
        resolved = int(totals["resolved_conversations"] or 0)
        avg_user_messages = float(totals["avg_user_messages"] or 0)

        return {
            "time_window_days": days,
            "total_conversations": total,
            "resolved_conversations": resolved,
            "deflection_rate": (resolved / total * 100) if total else 0,
            "avg_user_messages": avg_user_messages,
            "most_common_topic": top_topic["topic"] if top_topic else "general_inquiry",
            "most_common_topic_label": TOPIC_LABELS.get(
                top_topic["topic"] if top_topic else "general_inquiry",
                "General Inquiry",
            ),
            "topic_breakdown": self.get_topic_breakdown(days=days),
            "disposition_breakdown": self.get_disposition_breakdown(days=days),
        }

    def _infer_topic_fallback(self, messages: list[dict[str, Any]]) -> str:
        tool_names: list[str] = []
        user_text_parts: list[str] = []

        for message in messages:
            role = message.get("role")
            if role == "user":
                user_text_parts.append((message.get("content") or "").lower())

            if role == "assistant" and message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    function_data = tool_call.get("function", {})
                    tool_name = function_data.get("name")
                    if tool_name:
                        tool_names.append(tool_name)

        if any(name in {"check_return_eligibility", "initiate_return"} for name in tool_names):
            return "returns_refunds"
        if "lookup_order" in tool_names:
            return "order_status"

        user_text = " ".join(user_text_parts)
        if any(keyword in user_text for keyword in ["return", "refund", "damaged", "wrong", "defective"]):
            return "returns_refunds"
        if any(keyword in user_text for keyword in ["order", "tracking", "delivery", "status", "where is"]):
            return "order_status"
        if any(keyword in user_text for keyword in ["cancel", "address", "change"]):
            return "order_changes"

        return "general_inquiry"

    def _infer_disposition_fallback(self, messages: list[dict[str, Any]]) -> str:
        assistant_text = " ".join(
            (message.get("content") or "").lower()
            for message in messages
            if message.get("role") == "assistant"
        )

        if any(keyword in assistant_text for keyword in ["escalate", "supervisor", "human agent", "specialist"]):
            return "escalated"

        had_success = False
        had_failure = False

        for message in messages:
            if message.get("role") != "tool":
                continue

            content = message.get("content") or ""
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict):
                if payload.get("success") is True or payload.get("eligible") is True:
                    had_success = True
                if payload.get("success") is False or payload.get("eligible") is False or payload.get("error"):
                    had_failure = True
                if "order" in payload or "orders" in payload:
                    had_success = True

        if had_success and not had_failure:
            return "resolved"

        if any(keyword in assistant_text for keyword in ["glad i could help", "anything else", "resolved"]):
            return "resolved"

        return "open"
