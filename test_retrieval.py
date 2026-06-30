import json
from src.graph import AgentState, model_call, execute_tools_if_needed
from langchain_core.messages import HumanMessage

def run_test():
    state = AgentState(
        messages=[HumanMessage(content="72-year-old female with HER2-positive breast cancer, presenting with immune-mediated myocarditis after receiving pembrolizumab. Patient has a background of type 2 diabetes.")],
        papers_found=False,
        conversation_id="test-123",
        response_type="",
        latest_papers=[],
        latest_references=[],
        alpha=0.8,
        beta=0.1,
        gamma=0.1
    )
    
    print("Running model_call (Entity Extraction & Query Generation)...")
    result_1 = model_call(state)
    
    # Update state with model's message
    state["messages"] = list(state["messages"]) + result_1["messages"]
    print(f"Generated Tool Call:\n{result_1['messages'][0].content}")
    
    print("\nRunning execute_tools_if_needed (PubMed Search & Retrieval)...")
    result_2 = execute_tools_if_needed(state)
    
    print("\nFinal Papers Found:")
    for i, paper in enumerate(result_2.get("latest_papers", [])):
        print(f"\n[{i+1}] {paper.get('title')}")
        print(f"    Year: {paper.get('publication_year')} | Citations: {paper.get('citation_count')}")
        print(f"    Scores -> Sim: {paper.get('abstract_similarity'):.3f}, Rec: {paper.get('recency_score'):.3f}, Cit: {paper.get('citation_score'):.3f}")
        print(f"    Composite: {paper.get('composite_score'):.3f}")

if __name__ == "__main__":
    run_test()
