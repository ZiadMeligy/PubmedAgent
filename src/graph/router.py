"""
Routing logic for the LangGraph workflow.
Routes between paper search, tool execution, and Q&A modes.
"""

from src.graph import AgentState


def should_continue(state: AgentState) -> str:
    """
    Decide where to route based on message content.
    
    Possible routes:
    - 'tools': Execute tool (search_pubmed)
    - 'qa': Answer question based on retrieved papers
    - 'end': Finish
    """
    messages = list(state["messages"])
    if not messages:
        return "end"
    
    last_message = messages[-1]
    
    # Check if message contains a tool call
    has_tool_call = (hasattr(last_message, 'content') and 
                     '<TOOL_CALL>' in last_message.content)
                     
    has_qa_call = (hasattr(last_message, 'content') and 
                   '<QA_CALL>' in last_message.content)
    
    if has_tool_call:
        return "tools"
        
    if has_qa_call:
        return "qa"
    
    # Default: end (normal chat)
    return "end"