import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from operator import add as add_messages
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

tools = [add]

llm = ChatOllama(
    model="llama3.2:3b"
).bind_tools(tools)


def model_call(state: AgentState) -> AgentState:
    system_prompt = SystemMessage(content="You are a helpful assistant that can perform addition using the add tool.")
    response = llm.invoke([system_prompt] + state["messages"])
    return {"messages": state["messages"] + [response]}


def should_continue(state: AgentState) -> bool:
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"

graph = StateGraph(AgentState)
graph.add_node("model_call", model_call)
tools_node =ToolNode(tools=tools)
graph.add_node("tools", tools_node)

graph.set_entry_point("model_call")

graph.add_conditional_edges("model_call", should_continue, {
    "continue": "tools",
    "end": END
})
graph.add_edge("tools", "model_call")

graph = graph.compile()

if __name__ == "__main__":
    # Add a user message to test the agent
    initial_state = {"messages": [HumanMessage(content="What is 5 plus 3?")]}
    
    # Use invoke() instead of run()
    final_state = graph.invoke(initial_state)
    
    # Print the final response
    print(final_state["messages"][-1].content)
