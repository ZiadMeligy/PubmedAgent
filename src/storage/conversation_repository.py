"""
Persistent storage for conversations using SQLite.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

class ConversationRepository:
    
    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    papers_found BOOLEAN
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                )
            ''')
            conn.commit()

    def create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id, created_at, updated_at, papers_found) VALUES (?, ?, ?, ?)",
                (conversation_id, now, now, False)
            )
            conn.commit()

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get an existing conversation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if not row:
                return None
            
            # Fetch messages
            msg_rows = conn.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,)).fetchall()
            
            messages = []
            for m in msg_rows:
                if m['role'] == 'human':
                    messages.append(HumanMessage(content=m['content']))
                elif m['role'] == 'ai':
                    messages.append(AIMessage(content=m['content']))
                elif m['role'] == 'system':
                    messages.append(SystemMessage(content=m['content']))
                    
            return {
                "id": row['id'],
                "created_at": row['created_at'],
                "updated_at": row['updated_at'],
                "papers_found": bool(row['papers_found']),
                "messages": messages
            }

    def append_message(self, conversation_id: str, message: BaseMessage) -> None:
        """Append a message to a conversation."""
        now = datetime.now().isoformat()
        
        role = "unknown"
        if isinstance(message, HumanMessage):
            role = "human"
        elif isinstance(message, AIMessage):
            role = "ai"
        elif isinstance(message, SystemMessage):
            role = "system"
            
        content = message.content if isinstance(message.content, str) else str(message.content)
            
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now)
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            conn.commit()
            
    def update_papers_found(self, conversation_id: str, papers_found: bool) -> None:
        """Update papers_found status."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE conversations SET papers_found = ?, updated_at = ? WHERE id = ?",
                (papers_found, now, conversation_id)
            )
            conn.commit()

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and its messages."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

# Global instance
_repo = None

def get_conversation_repository() -> ConversationRepository:
    """Get or create the global conversation repository instance."""
    global _repo
    if _repo is None:
        _repo = ConversationRepository()
    return _repo
