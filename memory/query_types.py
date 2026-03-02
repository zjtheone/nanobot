from typing import List, Optional
from enum import Enum
from dataclasses import dataclass

class IntentType(Enum):
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    DEFINITIONAL = "definitional"
    CONVERSATIONAL = "conversational"
    UNKNOWN = "unknown"

@dataclass
class ParsedQuery:
    original_query: str
    keywords: List[str]
    phrases: List[str]
    intent: IntentType = IntentType.UNKNOWN
    embedding: Optional[List[float]] = None
