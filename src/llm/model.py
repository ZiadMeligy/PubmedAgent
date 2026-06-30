"""
LLM model setup and configuration.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from src.config import llm
from src.llm import SYSTEM_PROMPT


def get_system_prompt() -> SystemMessage:
    """Get the system prompt as a LangChain SystemMessage."""
    return SystemMessage(content=SYSTEM_PROMPT)


def invoke_llm(messages: list) -> str:
    """
    Invoke the LLM with given messages.
    
    Args:
        messages: List of BaseMessage objects
    
    Returns:
        LLM response content
    """
    response = llm.invoke(messages)
    return response
