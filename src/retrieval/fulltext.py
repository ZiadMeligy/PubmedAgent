"""
Full-text extraction utilities for PubMed papers.
Retrieves papers from PMC (PubMed Central) and extracts clean text.
"""

import requests
import re
from typing import Optional, Dict
from xml.etree import ElementTree as ET
import json


class FullTextExtractor:
    """Extract full text from various PubMed/PMC sources."""
    
    PMC_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"
    PMC_API_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10
    
    def get_pmc_id_from_pmid(self, pmid: str) -> Optional[str]:
        """Get PMC ID from PubMed ID."""
        try:
            url = f"{self.PMC_API_BASE}/esearch.fcgi"
            params = {
                "db": "pmc",
                "term": f"{pmid}[uid]",
                "retmode": "json"
            }
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            return ids[0] if ids else None
        except Exception:
            return None
    
    def get_full_text_xml(self, pmc_id: str) -> Optional[str]:
        """Retrieve full text XML from PMC."""
        try:
            url = f"{self.PMC_BASE}/PMC{pmc_id}/xml"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
    
    def extract_sections_from_xml(self, xml_text: str) -> Dict[str, str]:
        """Parse XML and extract sections with proper hierarchy."""
        try:
            root = ET.fromstring(xml_text)
            sections = {}
            
            # Define namespaces
            ns = {'': 'http://www.ncbi.nlm.nih.gov/pmc'}
            
            # Extract title
            title_elem = root.find('.//article-title')
            if title_elem is not None:
                sections['title'] = self._extract_text(title_elem)
            
            # Extract abstract
            abstract_elem = root.find('.//abstract')
            if abstract_elem is not None:
                sections['abstract'] = self._extract_text(abstract_elem)
            
            # Extract body sections
            body_elem = root.find('.//body')
            if body_elem is not None:
                for sec in body_elem.findall('.//sec'):
                    title = sec.find('title')
                    section_name = self._extract_text(title) if title is not None else "Untitled"
                    section_text = self._extract_text(sec)
                    sections[section_name] = section_text
            
            return sections
        except Exception:
            return {}
    
    def _extract_text(self, elem) -> str:
        """Recursively extract text from XML element."""
        if elem is None:
            return ""
        
        text_parts = []
        
        # Get direct text
        if elem.text:
            text_parts.append(elem.text.strip())
        
        # Get text from children
        for child in elem:
            child_text = self._extract_text(child)
            if child_text:
                text_parts.append(child_text)
            
            # Get tail text (text after closing tag)
            if child.tail:
                text_parts.append(child.tail.strip())
        
        return ' '.join([t for t in text_parts if t])
    
    def extract_full_text(self, pmid: str) -> Optional[Dict[str, str]]:
        """
        Main method: Extract full text from PMID.
        
        Returns dict with sections or None if unavailable.
        """
        # Try to get PMC ID
        pmc_id = self.get_pmc_id_from_pmid(pmid)
        if not pmc_id:
            return None
        
        # Get XML
        xml_text = self.get_full_text_xml(pmc_id)
        if not xml_text:
            return None
        
        # Parse and extract sections
        sections = self.extract_sections_from_xml(xml_text)
        return sections if sections else None
