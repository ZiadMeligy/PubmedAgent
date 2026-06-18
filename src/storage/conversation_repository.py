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
            conn.execute('PRAGMA journal_mode=WAL;')
            
            # Create users table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            ''')
            
            # Create user_preferences table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    alpha REAL DEFAULT 0.80,
                    beta REAL DEFAULT 0.10,
                    gamma REAL DEFAULT 0.10,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    papers_found BOOLEAN,
                    user_id TEXT,
                    title TEXT
                )
            ''')
            
            # Migration logic for existing database
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
            except sqlite3.OperationalError:
                pass
                
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
            except sqlite3.OperationalError:
                pass
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

    def create_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> None:
        """Create a new conversation."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id, created_at, updated_at, papers_found, user_id, title) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, now, now, False, user_id, "New Conversation")
            )
            conn.commit()

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        """Update conversation title."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
            conn.commit()

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
            return [dict(row) for row in rows]

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
                "user_id": row['user_id'],
                "title": row['title'],
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

    # --- User Management ---
    def create_user(self, user_id: str, email: str, username: str, password_hash: str) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users (id, email, username, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, username, password_hash, now)
            )
            conn.execute(
                "INSERT INTO user_preferences (user_id, alpha, beta, gamma) VALUES (?, 0.80, 0.10, 0.10)",
                (user_id,)
            )
            conn.commit()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None
            
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    # --- Preferences Management ---
    def get_preferences(self, user_id: str) -> Dict[str, float]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT alpha, beta, gamma FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
            return {"alpha": 0.80, "beta": 0.10, "gamma": 0.10}

    def update_preferences(self, user_id: str, alpha: float, beta: float, gamma: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE user_preferences SET alpha = ?, beta = ?, gamma = ? WHERE user_id = ?",
                (alpha, beta, gamma, user_id)
            )
            conn.commit()

# Global instance
_repo = None

def get_conversation_repository() -> ConversationRepository:
    """Get or create the global conversation repository instance."""
    global _repo
    if _repo is None:
        _repo = ConversationRepository()
    return _repo
