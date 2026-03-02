"""
Lightweight wrapper for cross‑encoder models, to avoid heavy dependencies.
"""

from typing import List, Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)


class CrossEncoderWrapper:
    """Wrapper for sentence_transformers.CrossEncoder with lazy loading."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
        self.initialized = False
    
    def init(self):
        if self.initialized:
            return
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            self.initialized = True
            logger.info(f"Loaded cross‑encoder model: {self.model_name}")
        except ImportError as e:
            logger.warning(f"Failed to load sentence-transformers: {e}")
            self.model = None
            self.initialized = True
    
    def predict(self, pairs: List[List[str]], batch_size: int = 32) -> List[float]:
        """
        Predict relevance scores for each pair (query, document).
        
        Args:
            pairs: list of [query, document] strings
            batch_size: batch size for inference
            
        Returns:
            list of scores (float)
        """
        self.init()
        if self.model is None:
            # Dummy fallback: random scores
            import random
            return [random.random() for _ in pairs]
        
        # Use the underlying cross‑encoder
        return self.model.predict(pairs, batch_size=batch_size)


def load_cross_encoder(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> CrossEncoderWrapper:
    """Factory function."""
    return CrossEncoderWrapper(model_name)