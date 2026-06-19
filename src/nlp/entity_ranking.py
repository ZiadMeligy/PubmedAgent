import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.llm.model import invoke_llm

logger = logging.getLogger(__name__)

ENTITY_RANKING_PROMPT = """You are an expert biomedical information extraction system.
Given a list of raw medical entities extracted from a clinical note, your task is to categorize them and assign an importance priority.

Categories:
- PRIMARY_DISEASE (The main condition being investigated)
- MEDICATION (Drugs, therapies, treatments)
- BIOMARKER (Genes, mutations, proteins, cell markers)
- PROCEDURE (Surgeries, scans, specific therapeutic interventions)
- SYMPTOM/COMPLICATION (Adverse events, side effects, symptoms)
- GENERIC/LOW_IMPORTANCE (Age, sex, broad terms, background history)

Priorities:
- HIGH: Primary diseases, medications, biomarkers, critical procedures.
- MEDIUM: Symptoms, complications, secondary conditions.
- LOW: Generic descriptors, demographic info, vague terms.

Output exactly a JSON object matching this schema:
{
  "high_importance": [
    {"entity": "...", "category": "..."}
  ],
  "medium_importance": [
    {"entity": "...", "category": "..."}
  ],
  "low_importance": [
    {"entity": "...", "category": "..."}
  ]
}
"""

def rank_entity_importance(entities: list) -> dict:
    """
    Classify and rank a list of raw biomedical entities using the LLM.
    
    Args:
        entities: List of strings (extracted entities)
    
    Returns:
        Dictionary of ranked entities.
    """
    if not entities:
        return {"high_importance": [], "medium_importance": [], "low_importance": []}
        
    messages = [
        SystemMessage(content=ENTITY_RANKING_PROMPT),
        HumanMessage(content=f"Raw Entities:\n{json.dumps(entities)}")
    ]
    
    try:
        response_text = invoke_llm(messages).content
        
        # Parse JSON from response (handling potential markdown blocks)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].strip()
        else:
            json_str = response_text.strip()
            
        ranked_entities = json.loads(json_str)
        return ranked_entities
    except Exception as e:
        logger.error(f"Failed to rank entities: {e}")
        # Fallback: put everything in medium importance
        return {
            "high_importance": [],
            "medium_importance": [{"entity": e, "category": "UNKNOWN"} for e in entities],
            "low_importance": []
        }
