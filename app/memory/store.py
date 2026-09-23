"""
Memory Store Operations
Database access layer for Conversations, Messages, and Semantic Memories.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.memory import Conversation, Message, Memory

class MemoryStore:
    """Provides persistence operations for conversation turns and persistent facts."""

    @staticmethod
    def get_or_create_conversation(db: Session, conversation_id: str, agent_id: str) -> Conversation:
        conv = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if not conv:
            conv = Conversation(
                conversation_id=conversation_id,
                agent_id=agent_id,
                metadata_json={}
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
        return conv

    @staticmethod
    def add_message(db: Session, conversation_id: str, role: str, content: str) -> Message:
        token_count = len(content.split())
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_recent_messages(db: Session, conversation_id: str, limit: int = 10) -> List[Message]:
        return (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )[::-1]  # Return in chronological order

    @staticmethod
    def add_long_term_memory(
        db: Session,
        content: str,
        entity_key: Optional[str] = None,
        memory_type: str = "long_term_fact",
        conversation_id: Optional[str] = None,
        importance_score: float = 1.0
    ) -> Memory:
        mem = Memory(
            content=content,
            entity_key=entity_key,
            memory_type=memory_type,
            conversation_id=conversation_id,
            importance_score=importance_score
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    @staticmethod
    def search_memories(
        db: Session,
        query: str,
        entity_key: Optional[str] = None,
        limit: int = 5
    ) -> List[Memory]:
        """
        Search memories relevant to the entity or keywords in query.
        """
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        
        mem_query = db.query(Memory)
        if entity_key:
            mem_query = mem_query.filter(Memory.entity_key == entity_key)

        all_memories = mem_query.all()
        scored_memories = []

        for mem in all_memories:
            content_lower = mem.content.lower()
            overlap = sum(1 for term in query_terms if term in content_lower)
            # Bonus score if entity matches
            if entity_key and mem.entity_key == entity_key:
                overlap += 2
            
            if overlap > 0 or not query_terms:
                scored_memories.append((overlap * mem.importance_score, mem))

        # Sort by relevance score descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in scored_memories[:limit]]
