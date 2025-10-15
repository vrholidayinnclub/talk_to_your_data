"""
Memory System for Conversation Persistence
Stores and retrieves conversation history across sessions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation history and context across sessions.
    
    Features:
    - Session-based storage
    - Conversation history persistence
    - Context retrieval for follow-up questions
    - Memory summarization for long conversations
    """
    
    def __init__(self, storage_dir: str = "data/memory"):
        """
        Initialize conversation memory.
        
        Args:
            storage_dir: Directory to store conversation files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Memory storage initialized at: {self.storage_dir}")
    
    def save_interaction(self, session_id: str, question: str, answer: str, 
                        data: Optional[Dict] = None, metadata: Optional[Dict] = None):
        """
        Save a question-answer interaction to memory.
        
        Args:
            session_id: Unique session identifier
            question: User's question
            answer: Agent's answer
            data: Optional data returned (query results, predictions, etc.)
            metadata: Optional metadata (iterations, tool used, etc.)
        """
        try:
            session_file = self.storage_dir / f"{session_id}.json"
            
            # Load existing history
            if session_file.exists():
                with open(session_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {
                    'session_id': session_id,
                    'created_at': datetime.now().isoformat(),
                    'interactions': []
                }
            
            # Add new interaction
            interaction = {
                'timestamp': datetime.now().isoformat(),
                'question': question,
                'answer': answer,
                'data_summary': self._summarize_data(data) if data else None,
                'metadata': metadata or {}
            }
            
            history['interactions'].append(interaction)
            history['updated_at'] = datetime.now().isoformat()
            
            # Save to file
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved interaction to session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
    
    def get_session_history(self, session_id: str, last_n: int = 5) -> List[Dict]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Session identifier
            last_n: Number of recent interactions to retrieve
            
        Returns:
            List of recent interactions
        """
        try:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                return []
            
            with open(session_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            interactions = history.get('interactions', [])
            return interactions[-last_n:] if last_n else interactions
            
        except Exception as e:
            logger.error(f"Failed to retrieve session history: {e}")
            return []
    
    def get_context_for_question(self, session_id: str, current_question: str) -> str:
        """
        Get relevant context from previous interactions for the current question.
        
        Args:
            session_id: Session identifier
            current_question: Current user question
            
        Returns:
            Formatted context string
        """
        try:
            history = self.get_session_history(session_id, last_n=3)
            
            if not history:
                return ""
            
            context_parts = ["# Previous Conversation Context\n"]
            
            for i, interaction in enumerate(history, 1):
                context_parts.append(f"\n## Interaction {i}")
                context_parts.append(f"**Q:** {interaction['question']}")
                context_parts.append(f"**A:** {interaction['answer'][:200]}...")  # Truncate long answers
                
                if interaction.get('data_summary'):
                    context_parts.append(f"**Data:** {interaction['data_summary']}")
            
            context_parts.append(f"\n## Current Question\n{current_question}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to generate context: {e}")
            return ""
    
    def clear_session(self, session_id: str):
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
        """
        try:
            session_file = self.storage_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Cleared session {session_id}")
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def list_sessions(self) -> List[Dict]:
        """
        List all available sessions.
        
        Returns:
            List of session metadata
        """
        try:
            sessions = []
            for session_file in self.storage_dir.glob("*.json"):
                with open(session_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    sessions.append({
                        'session_id': history.get('session_id'),
                        'created_at': history.get('created_at'),
                        'updated_at': history.get('updated_at'),
                        'interaction_count': len(history.get('interactions', []))
                    })
            return sessions
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def _summarize_data(self, data: Dict) -> str:
        """
        Create a brief summary of data for memory storage.
        
        Args:
            data: Data dictionary
            
        Returns:
            Summary string
        """
        try:
            if 'error' in data:
                return f"Error: {data['error']}"
            
            summary_parts = []
            
            if 'data' in data and isinstance(data['data'], list):
                summary_parts.append(f"{len(data['data'])} rows")
            
            if 'columns' in data:
                summary_parts.append(f"Columns: {', '.join(data['columns'][:5])}")
            
            if 'forecast_data' in data:
                summary_parts.append("Forecast generated")
            
            if 'predictions' in data:
                summary_parts.append(f"{len(data['predictions'])} predictions")
            
            return " | ".join(summary_parts) if summary_parts else "Data returned"
            
        except Exception:
            return "Data available"


# Global memory instance
_memory_instance = None


def get_memory() -> ConversationMemory:
    """Get or create global memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance
