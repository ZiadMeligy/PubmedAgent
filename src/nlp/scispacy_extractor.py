import logging

logger = logging.getLogger(__name__)

# Lazy load to avoid slowing down startup
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        logger.info("Loading SciSpaCy model (en_core_sci_sm)...")
        try:
            import spacy
            _nlp = spacy.load("en_core_sci_sm")
        except ImportError:
            logger.warning("spacy is not installed.")
            _nlp = False
        except OSError:
            logger.warning("SciSpaCy model en_core_sci_sm not found.")
            _nlp = False
    return _nlp

def extract_entities(text: str) -> dict:
    """
    Extract biomedical entities from clinical text.
    
    Returns:
        A dictionary with entity categories and lists of extracted entities.
    """
    nlp = get_nlp()
    if not nlp:
        return {"Extracted Entities": []}
        
    doc = nlp(text)
    
    # en_core_sci_sm mostly labels everything as 'ENTITY'.
    # We will just collect all unique entities.
    entities = []
    for ent in doc.ents:
        entities.append(ent.text)
        
    # Deduplicate while preserving order
    seen = set()
    unique_entities = []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            unique_entities.append(e)
            
    return {"Biomedical Entities": unique_entities}
