"""
Biomedical Literature Retrieval Agent - Interactive Chatbot

Supports:
1. Literature search via PubMed
2. Follow-up Q&A over retrieved papers
3. Multi-turn conversation history
"""

from langchain_core.messages import HumanMessage
from src.graph.builder import compiled_graph


def print_last_response(state):
    """Print the latest assistant response."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "content"):
        print("\nAssistant:")
        print("-" * 100)
        print(last_message.content)
        print("-" * 100)


def main():
    print("=" * 100)
    print("BIOMEDICAL LITERATURE RETRIEVAL AGENT")
    print("=" * 100)

    print(
        """
Examples:
- Find papers about diabetic kidney disease
- Find studies about COPD and pulmonary hypertension
- What therapies reduced albuminuria?
- Which paper discussed exercise tolerance?

Type 'exit' to quit.
"""
    )

    # Persistent conversation state
    state = {
        "messages": [],
        "papers_found": False,
        "mode": "search"  # Keep for now until we redesign routing
    }

    while True:

        user_input = input("\nUser: ").strip()

        if user_input.lower() in {"exit", "quit"}:
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        # Append user message
        state["messages"].append(
            HumanMessage(content=user_input)
        )

        try:
            # Run graph
            state = compiled_graph.invoke(state)

            # Display latest assistant response
            print_last_response(state)

        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()