"""
Cross‑encoder wrapper for compatibility with different backends.
"""
import logging
from typing import List, Optional, Union, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class CrossEncoderWrapper:
    """
    Unified interface for cross‑encoder models.
    Supports both sentence‑transformers and transformers backends.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        backend: str = "sentence_transformers",  # "sentence_transformers" or "transformers"
        device: Optional[str] = None,
        max_length: int = 512,
        **kwargs
    ):
        self.model_name = model_name
        self.backend = backend
        self.device = device
        self.max_length = max_length
        self.model = None
        self._load_model(**kwargs)
    
    def _load_model(self, **kwargs):
        """Load the model using the selected backend."""
        try:
            if self.backend == "sentence_transformers":
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder(
                    self.model_name,
                    device=self.device,
                    max_length=self.max_length,
                    **kwargs
                )
                logger.info(f"Loaded cross‑encoder via sentence‑transformers: {self.model_name}")
            elif self.backend == "transformers":
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                import torch
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
                if self.device is None:
                    self.device = "cuda" if torch.cuda.is_available() else "cpu"
                self.model.to(self.device)
                self.model.eval()
                logger.info(f"Loaded cross‑encoder via transformers: {self.model_name} (device: {self.device})")
            else:
                raise ValueError(f"Unknown backend: {self.backend}")
        except ImportError as e:
            logger.error(f"Backend '{self.backend}' not available: {e}")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load cross‑encoder model: {e}")
            self.model = None
    
    def is_available(self) -> bool:
        return self.model is not None
    
    def predict(
        self,
        pairs: List[Tuple[str, str]],
        batch_size: int = 32,
        **kwargs
    ) -> np.ndarray:
        """
        Compute relevance scores for query‑document pairs.
        
        Args:
            pairs: List of (query, document) string pairs.
            batch_size: Batch size for inference.
            **kwargs: Additional backend‑specific arguments.
        
        Returns:
            Numpy array of scores (shape [len(pairs)]).
        """
        if not self.is_available():
            # Return dummy scores
            return np.ones(len(pairs), dtype=np.float32)
        
        try:
            if self.backend == "sentence_transformers":
                return self.model.predict(
                    pairs,
                    batch_size=batch_size,
                    convert_to_tensor=False,
                    convert_to_numpy=True,
                    **kwargs
                )
            elif self.backend == "transformers":
                import torch
                from torch.nn.functional import softmax
                scores = []
                for i in range(0, len(pairs), batch_size):
                    batch = pairs[i:i + batch_size]
                    # Tokenize
                    inputs = self.tokenizer(
                        batch,
                        padding=True,
                        truncation=True,
                        max_length=self.max_length,
                        return_tensors="pt"
                    ).to(self.device)
                    with torch.no_grad():
                        outputs = self.model(**inputs)
                        # For binary classification, take the positive class (usually index 1)
                        logits = outputs.logits
                        if logits.shape[-1] == 2:
                            batch_scores = softmax(logits, dim=-1)[:, 1].cpu().numpy()
                        else:
                            # Regression model, take the first column
                            batch_scores = logits[:, 0].cpu().numpy()
                        scores.append(batch_scores)
                if scores:
                    return np.concatenate(scores)
                else:
                    return np.array([], dtype=np.float32)
            else:
                return np.ones(len(pairs), dtype=np.float32)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return np.ones(len(pairs), dtype=np.float32)
    
    def rank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        batch_size: int = 32
    ) -> List[Tuple[int, float]]:
        """
        Rank documents with respect to a single query.
        
        Returns:
            List of (original_index, score) sorted descending.
        """
        if not documents:
            return []
        pairs = [[query, doc] for doc in documents]
        scores = self.predict(pairs, batch_size=batch_size)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked
