"""
Intent classification for user messages to determine the appropriate retrieval or conversational action.
"""

from typing import List, Dict, Any, Literal
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from src.llm.model import invoke_llm

IntentType = Literal['SEARCH_PUBMED', 'CONVERSATION', 'SUMMARIZE_ALL', 'SEMANTIC_QA', 'PAPER_METADATA']

def get_intent_classifier_prompt() -> SystemMessage:
    return SystemMessage(content="""You are an intent classification engine for a biomedical literature retrieval system.
Analyze the user's latest message and categorize their intent into EXACTLY ONE of the following categories. 

1. SEARCH_PUBMED: The user is providing a clinical note, describing a patient case, or explicitly asking to search for literature, papers, or treatments.
2. SUMMARIZE_ALL: The user is explicitly asking to summarize all the retrieved papers, give an overview of the papers, or summarize the literature found.
3. PAPER_METADATA: The user is asking about specific metadata of a retrieved paper, such as "What journal is paper 1 in?", "Who authored paper 2?", or "When was paper 3 published?".
4. SEMANTIC_QA: The user is asking a specific medical, clinical, or scientific question that requires referencing the content of the retrieved literature (e.g., "What were the side effects mentioned?", "Did albuminuria decrease?").
5. CONVERSATION: The user is just chatting, saying hello, thanking you, or asking a general question that does not require literature retrieval.

Output ONLY the exact category name as your response. Do not include any other text.""")


def classify_intent(messages: List[BaseMessage]) -> IntentType:
    """Classify the user's intent."""
    if not messages:
        return 'CONVERSATION'
        
    last_msg = messages[-1].content
    
    # Fast heuristic check
    if "summarize all" in last_msg.lower() or "overview of all" in last_msg.lower() or "summarize the papers" in last_msg.lower():
        return 'SUMMARIZE_ALL'
        
    system_prompt = get_intent_classifier_prompt()
    full_messages = [system_prompt, HumanMessage(content=last_msg)]
    
    try:
        response = invoke_llm(full_messages)
        intent = response.content.strip()
        if intent in ['SEARCH_PUBMED', 'CONVERSATION', 'SUMMARIZE_ALL', 'SEMANTIC_QA', 'PAPER_METADATA']:
            return intent
    except Exception:
        pass
        
    # Default fallback
    return 'SEMANTIC_QA'
