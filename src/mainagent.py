"""
Biomedical Literature Retrieval Agent - Main Entry Point

This module orchestrates the biomedical literature retrieval workflow,
with support for:
1. Paper search using clinical notes and LLM query generation
2. Q&A on retrieved papers using Qdrant vector store and semantic reranking
"""

from langchain_core.messages import HumanMessage
from src.graph.builder import compiled_graph


def main():
    """
    Main entry point for the biomedical literature retrieval agent.
    
    Demonstrates:
    1. Clinical note → query generation → paper search → abstract storage
    2. Q&A on the stored abstracts
    """
    
    # ===== PHASE 1: PAPER SEARCH =====
    clinical_note = """
    58-year-old male with type 2 diabetes mellitus for 18 years.

Current medications:
- Metformin 1000 mg BID
- Ramipril 10 mg daily
- Amlodipine 5 mg daily
- Atorvastatin 40 mg daily

Clinical status:
- Persistent macroalbuminuria (UACR 850 mg/g)
- eGFR declined from 58 to 42 mL/min/1.73m² over the last 2 years
- HbA1c 6.9%
- Blood pressure 126/74 mmHg
- Potassium 4.6 mmol/L

Despite optimized ACE inhibitor therapy, blood pressure control, and acceptable glycemic control, kidney function continues to decline and albuminuria remains significantly elevated.

Clinical Question:
What evidence-based therapeutic strategies are available to reduce albuminuria, slow eGFR decline, decrease risk of progression to end-stage kidney disease, and improve long-term renal outcomes in patients with diabetic kidney disease already receiving standard-of-care therapy?"""
    
    print("=" * 100)
    print("BIOMEDICAL LITERATURE RETRIEVAL AGENT - TWO-PHASE WORKFLOW")
    print("=" * 100)
    print("\n[PHASE 1: PAPER SEARCH]")
    print(f"\nClinical Note:\n{clinical_note}\n")
    print("-" * 100)
    print("Processing through agent...\n")
    
    # Initialize state for PHASE 1 (Paper search)
    initial_state = {
        "messages": [HumanMessage(content=clinical_note)],
        "papers_found": False,
        "mode": "search"
    }
    
    # Run paper search phase
    result = compiled_graph.invoke(initial_state)
    
    print("\n[PAPERS FOUND AND STORED IN VECTOR DATABASE]")
    print("=" * 100)
    
    # ===== PHASE 2: Q&A ON PAPERS =====
    print("\n[PHASE 2: QUESTION-ANSWERING ON RETRIEVED PAPERS]\n")
    
    # Ask follow-up questions
    questions = [
        "What are the main therapies discussed for reducing albuminuria in diabetic kidney disease?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        print("-" * 100)
        
        # Add question to messages
        qa_state = {
            "messages": result["messages"] + [HumanMessage(content=question)],
            "papers_found": True,
            "mode": "qa"
        }
        
        # Run Q&A phase
        qa_result = compiled_graph.invoke(qa_state)
        
        # Display answer
        print("\nAnswer:")
        for message in qa_result["messages"][-1:]:
            if hasattr(message, 'content'):
                print(message.content)
        
        # Update state for next iteration
        result = qa_result
    
    print("\n" + "=" * 100)
    print("WORKFLOW COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
