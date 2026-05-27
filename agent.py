import os
import json
import re
from typing import TypedDict, Annotated, Sequence
from operator import add as add_messages
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq

from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage
)

load_dotenv()

from pymed import PubMed

# -------------------------
# STATE
# -------------------------

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# -------------------------
# PUBMED TOOL FUNCTION
# -------------------------

def search_pubmed(query: str) -> str:
    """
    Search PubMed for medical research papers.
    """
    pubmed = PubMed(tool="pubmed", email="your_email@example.com")
    results = pubmed.query(query, max_results=3)

    papers = []

    for article in results:
        title = article.title or "No title"
        abstract = (
            article.abstract[:300]
            if article.abstract
            else "No abstract available"
        )
        pubmed_id = article.pubmed_id
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"

        papers.append(
            f"""Title: {title}

Abstract:
{abstract}

URL: {url}"""
        )

    return "\n\n".join(papers) if papers else "No papers found for the given query."


# -------------------------
# LLM SETUP
# -------------------------

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0
)


# -------------------------
# MODEL NODE (WITHOUT TOOLS)
# -------------------------

def model_call(state: AgentState):
    """Call the LLM without function calling - instead use prompt-based tool invocation"""
    system_prompt = SystemMessage(
        content="""You are a medical literature assistant with expertise in PubMed searches.

When asked about medical research topics, you should:
1. Identify what medical information is needed
2. Call the search_pubmed tool by responding with a JSON block like this:
   <TOOL_CALL>
   {"tool": "search_pubmed", "query": "your search query here"}
   </TOOL_CALL>
3. Wait for the results
4. Analyze and summarize the findings

If you are shown search results, analyze them and provide a comprehensive answer.

Be concise and focused on answering the user's question with the most relevant information."""
    )

    messages = [system_prompt] + list(state["messages"])
    response = llm.invoke(messages)
    
    return {"messages": [response]}


# -------------------------
# TOOL EXECUTION NODE
# -------------------------

def execute_tools_if_needed(state: AgentState) -> dict:
    """Check if the last message contains a tool call and execute it"""
    messages = list(state["messages"])
    last_message = messages[-1]
    
    # Check if the message contains a tool call
    if hasattr(last_message, 'content') and '<TOOL_CALL>' in last_message.content:
        # Extract the tool call JSON
        match = re.search(r'<TOOL_CALL>(.*?)</TOOL_CALL>', last_message.content, re.DOTALL)
        if match:
            try:
                tool_data = json.loads(match.group(1))
                tool_name = tool_data.get("tool")
                
                if tool_name == "search_pubmed":
                    query = tool_data.get("query")
                    result = search_pubmed(query)
                    # Add the tool result as a message
                    return {"messages": [HumanMessage(content=f"Search results for '{query}':\n\n{result}\n\nPlease analyze these results and provide a comprehensive answer to the user's original question.")]}
            except json.JSONDecodeError:
                pass
    
    # No tool call found or invalid format
    return {"messages": []}


# -------------------------
# ROUTER
# -------------------------

def should_continue(state: AgentState) -> str:
    """Decide if we should continue with tool execution or end"""
    messages = list(state["messages"])
    last_message = messages[-1]
    
    # If the last message contains a tool call, continue to execute it
    if hasattr(last_message, 'content') and '<TOOL_CALL>' in last_message.content:
        return "tools"
    # Otherwise, we're done
    return "end"


# -------------------------
# GRAPH
# -------------------------

graph = StateGraph(AgentState)

graph.add_node("model", model_call)
graph.add_node("tools", execute_tools_if_needed)

graph.set_entry_point("model")

graph.add_conditional_edges(
    "model",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

graph.add_edge("tools", "model")

compiled_graph = graph.compile()


# -------------------------
# MAIN
# -------------------------

if __name__ == "__main__":
    initial_state = {
        "messages": [
            HumanMessage(
                content="What are the latest treatments for stage III NSCLC using immunotherapy?"
            )
        ]
    }

    final_state = compiled_graph.invoke(initial_state)

    print("\n\n" + "="*60)
    print("FINAL ANSWER:")
    print("="*60 + "\n")

    for msg in final_state["messages"]:
        if hasattr(msg, 'content'):
            # Clean up the output
            content = msg.content
            # Remove tool call markers for display
            content = re.sub(r'<TOOL_CALL>.*?</TOOL_CALL>', '', content, flags=re.DOTALL)
            if content.strip():
                print(content)