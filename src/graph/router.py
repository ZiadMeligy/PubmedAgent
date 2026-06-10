"""
Routing logic for the LangGraph workflow.

The model decides whether to search PubMed by emitting a TOOL_CALL.
The router only executes that decision.

If papers already exist and the latest message is a user question,
route to the QA node.
"""

from langchain_core.messages import HumanMessage
from src.graph import AgentState


def should_continue(state: AgentState) -> str:

    messages = list(state["messages"])

    if not messages:
        return "end"

    last_message = messages[-1]

    content = (
        last_message.content
        if hasattr(last_message, "content")
        else ""
    )

    papers_found = state.get("papers_found", False)

    has_tool_call = "<TOOL_CALL>" in content

    # Model requested PubMed search
    if has_tool_call:
        return "tools"

    # User asked a follow-up question
    if papers_found and isinstance(last_message, HumanMessage):
        return "qa"

    return "end"