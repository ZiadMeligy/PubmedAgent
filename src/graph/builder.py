"""
LangGraph workflow builder and compilation.
Orchestrates paper search and Q&A modes with dynamic routing.
"""

from langgraph.graph import StateGraph, END
from src.graph import AgentState, model_call, execute_tools_if_needed, qa_call
from src.graph.router import should_continue


def build_graph():
    """Build and compile the LangGraph workflow with dual modes."""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("model", model_call)  # Analyzes intent (search, qa, chat)
    graph.add_node("tools", execute_tools_if_needed)  # Execute PubMed search & store abstracts
    graph.add_node("qa", qa_call)  # Q&A mode - answers questions
    
    # Set entry point
    graph.set_entry_point("model")
    
    # Add conditional edges from model
    graph.add_conditional_edges(
        "model",
        should_continue,
        {
            "tools": "tools",
            "qa": "qa",
            "end": END
        }
    )
    
    # Nodes return to end directly
    graph.add_edge("tools", END)
    graph.add_edge("qa", END)
    
    return graph.compile()


# Compile the graph globally
compiled_graph = build_graph()
