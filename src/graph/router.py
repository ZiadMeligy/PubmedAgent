"""
Routing logic for the LangGraph workflow.
Routes between paper search, tool execution, and Q&A modes.
"""

from src.graph import AgentState


def should_continue(state: AgentState) -> str:
    """
    Decide where to route based on mode and message content.
    
    Possible routes:
    - 'search': First query generation (call model)
    - 'tools': Execute tool (search_pubmed)
    - 'qa': Answer question based on retrieved papers
    - 'end': Finish
    """
    messages = list(state["messages"])
    if not messages:
        return "search"
    
    last_message = messages[-1]
    mode = state.get("mode", "search")
    papers_found = state.get("papers_found", False)
    
    # Check if message contains a tool call
    has_tool_call = (hasattr(last_message, 'content') and 
                     '<TOOL_CALL>' in last_message.content)
    
    # If in search mode and model generated a tool call, execute it
    if mode == "search" and has_tool_call:
        return "tools"
    
    # If papers are found and we're in qa mode, answer the question
    if mode == "qa" and papers_found:
        # Check if user is asking a question (not requesting new papers)
        content = last_message.content if hasattr(last_message, 'content') else ""
        
        # If the message contains tool call, it's a new search request
        if has_tool_call:
            return "tools"
        
        # Otherwise, it's a Q&A question
        if content and not has_tool_call:
            return "qa"
    
    # Default: end
    return "end"
