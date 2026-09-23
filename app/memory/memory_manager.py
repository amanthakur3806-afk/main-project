"""
Memory Manager
Orchestrates short-term conversational context and semantic long-term memory.
Manages context window size to prevent token overflow.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.memory.store import MemoryStore

class MemoryManager:
    """Coordinates memory loading, relevance filtering, and context window compression."""

    def __init__(self, max_short_term_messages: int = 6, max_long_term_facts: int = 4):
        self.max_short_term_messages = max_short_term_messages
        self.max_long_term_facts = max_long_term_facts

    def load_memory_context(
        self,
        db: Session,
        conversation_id: Optional[str],
        query: str,
        entity_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load structured short-term and long-term memory for an agent run.
        """
        short_term_history = []
        if conversation_id:
            recent_msgs = MemoryStore.get_recent_messages(
                db,
                conversation_id=conversation_id,
                limit=self.max_short_term_messages
            )
            for msg in recent_msgs:
                short_term_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Long-term semantic fact retrieval
        long_term_records = MemoryStore.search_memories(
            db,
            query=query,
            entity_key=entity_key,
            limit=self.max_long_term_facts
        )
        long_term_facts = [rec.content for rec in long_term_records]

        return {
            "conversation_id": conversation_id,
            "short_term_history": short_term_history,
            "long_term_facts": long_term_facts
        }

    def save_turn(
        self,
        db: Session,
        conversation_id: Optional[str],
        agent_id: str,
        user_query: str,
        assistant_response: str
    ):
        """Save a completed conversational exchange to SQL."""
        if not conversation_id:
            return

        MemoryStore.get_or_create_conversation(db, conversation_id, agent_id)
        MemoryStore.add_message(db, conversation_id, "user", user_query)
        MemoryStore.add_message(db, conversation_id, "assistant", assistant_response)

memory_manager = MemoryManager()
