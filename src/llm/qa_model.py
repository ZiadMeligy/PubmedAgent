"""
Q&A model setup for answering questions based on retrieved chunks.
"""

from langchain_core.messages import SystemMessage
from src.config import llm
from src.llm.qa_system_prompt import QA_SYSTEM_PROMPT


def get_qa_system_prompt() -> SystemMessage:
    """Get the Q&A system prompt as a LangChain SystemMessage."""
    return SystemMessage(content=QA_SYSTEM_PROMPT)


def invoke_qa_model(messages: list) -> str:
    """
    Invoke the Q&A LLM with given messages.
    
    Args:
        messages: List of BaseMessage objects with context
    
    Returns:
        LLM response content
    """
    response = llm.invoke(messages)
    return response
