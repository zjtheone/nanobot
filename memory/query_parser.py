import re
from typing import List
from .query_types import ParsedQuery, IntentType

class QueryParser:
    def __init__(self, stopwords: Optional[List[str]] = None):
        self.stopwords = set(stopwords or [])

    def parse(self, query: str) -> ParsedQuery:
        original_query = query.lower()
        
        # Extract phrases (text in quotes)
        phrases = re.findall(r'"([^"]*)"', original_query)
        cleaned_query = re.sub(r'"([^"]*)"', '', original_query)

        # Extract keywords (split by space, remove stopwords and punctuation)
        words = re.findall(r'\b\w+\b', cleaned_query)
        keywords = [word for word in words if word not in self.stopwords and len(word) > 1]
        
        intent = self._detect_intent(original_query)

        return ParsedQuery(
            original_query=original_query,
            keywords=list(set(keywords)), # Remove duplicates
            phrases=list(set(phrases)),   # Remove duplicates
            intent=intent
        )

    def _detect_intent(self, query: str) -> IntentType:
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["how to", "steps to", "guide to", "procedure", "implement", "create", "setup"]):
            return IntentType.PROCEDURAL
        elif any(kw in query_lower for kw in ["what is", "define", "meaning of", "explanation for"]):
            return IntentType.DEFINITIONAL
        elif any(kw in query_lower for kw in ["tell me about", "explain", "info about"]):
            return IntentType.FACTUAL
        elif any(kw in query_lower for kw in ["hello", "hi", "how are you", "thank you", "what can you do"]):
            return IntentType.CONVERSATIONAL
        else:
            return IntentType.UNKNOWN
