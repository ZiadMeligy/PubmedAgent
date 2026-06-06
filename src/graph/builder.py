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
    graph.add_node("model", model_call)  # Paper search mode - generates queries
    graph.add_node("tools", execute_tools_if_needed)  # Execute PubMed search & store abstracts
    graph.add_node("qa", qa_call)  # Q&A mode - answers questions
    
    # Set entry point
    graph.set_entry_point("model")
    
    # Add conditional edges from model (routes to tools or end)
    graph.add_conditional_edges(
        "model",
        should_continue,
        {
            "tools": "tools",
            "qa": "qa",
            "end": END
        }
    )
    
    # From tools, go back to model (to display papers or answer)
    graph.add_edge("tools", "model")
    
    # From QA, check if we should continue or end
    graph.add_conditional_edges(
        "qa",
        should_continue,
        {
            "tools": "tools",  # User wants to search again
            "qa": "qa",  # Ask another question
            "end": END
        }
    )
    
    return graph.compile()


# Compile the graph globally
compiled_graph = build_graph()
