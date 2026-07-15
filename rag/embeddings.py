import hashlib
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from config.settings import settings
from utils.logger import logger
import torch

class EmbeddingsPipeline:
    """Manages local SentenceTransformer models and caches computed embeddings in SQLite."""
    def __init__(self, cache_dir: Path = settings.CACHE_DIR / "embeddings_cache.db"):
        self.cache_dir = cache_dir
        self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
        self._init_cache_db()
        self.current_model_name = None
        self.model = None
        
    def _init_cache_db(self):
        """Create cache tables for embeddings."""
        conn = sqlite3.connect(str(self.cache_dir))
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings_cache (
                    text_hash TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    PRIMARY KEY (text_hash, model_name)
                );
            """)
        conn.close()

    def _get_hash(self, text: str) -> str:
        """Compute SHA256 hash of a string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_model(self, model_name: str):
        """Loads SentenceTransformer model lazily to CPU/GPU."""
        if self.current_model_name == model_name and self.model is not None:
            return
            
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model '{model_name}' on device '{device}'...")
        
        # Override default HuggingFace cache folder to keep everything self-contained in workspace cache
        os_env_cache = settings.CACHE_DIR / "huggingface"
        os_env_cache.mkdir(parents=True, exist_ok=True)
        
        # Initialize SentenceTransformer
        self.model = SentenceTransformer(
            model_name,
            device=device,
            cache_folder=str(os_env_cache)
        )
        self.current_model_name = model_name
        logger.info(f"Model '{model_name}' loaded successfully.")

    def get_cached_embeddings(self, texts: List[str], model_name: str) -> Tuple[List[List[float]], List[str], List[int]]:
        """Checks cache database and returns cached embeddings, along with missing indices and texts."""
        hashes = [self._get_hash(t) for t in texts]
        embeddings = [None] * len(texts)
        missing_texts = []
        missing_indices = []
        
        conn = sqlite3.connect(str(self.cache_dir))
        cursor = conn.cursor()
        
        for idx, text in enumerate(texts):
            h = hashes[idx]
            cursor.execute(
                "SELECT embedding FROM embeddings_cache WHERE text_hash = ? AND model_name = ?",
                (h, model_name)
            )
            row = cursor.fetchone()
            if row:
                # Read bytes back into float list
                blob = row[0]
                embeddings[idx] = np.frombuffer(blob, dtype=np.float32).tolist()
            else:
                missing_texts.append(text)
                missing_indices.append(idx)
                
        conn.close()
        return embeddings, missing_texts, missing_indices

    def save_embeddings_to_cache(self, texts: List[str], embeddings: List[List[float]], model_name: str):
        """Saves generated embeddings to the SQLite cache."""
        conn = sqlite3.connect(str(self.cache_dir))
        with conn:
            for text, emb in zip(texts, embeddings):
                h = self._get_hash(text)
                emb_array = np.array(emb, dtype=np.float32)
                blob = emb_array.tobytes()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO embeddings_cache (text_hash, model_name, embedding)
                    VALUES (?, ?, ?)
                    """,
                    (h, model_name, blob)
                )
        conn.close()

    def get_embeddings(self, texts: List[str], model_name: str = None) -> List[List[float]]:
        """Retrieves embeddings for a list of texts, using cache when possible."""
        if not texts:
            return []
            
        model_name = model_name or settings.DEFAULT_EMBEDDING_MODEL
        
        # 1. Fetch from cache
        embeddings, missing_texts, missing_indices = self.get_cached_embeddings(texts, model_name)
        
        # 2. Encode missing texts
        if missing_texts:
            self._load_model(model_name)
            logger.info(f"Generating embeddings for {len(missing_texts)} missing chunks...")
            # Compute embeddings
            new_embeddings = self.model.encode(
                missing_texts, 
                show_progress_bar=False, 
                convert_to_numpy=True
            ).tolist()
            
            # Save new embeddings to cache
            self.save_embeddings_to_cache(missing_texts, new_embeddings, model_name)
            
            # Reconstruct original order
            for idx, emb in zip(missing_indices, new_embeddings):
                embeddings[idx] = emb
                
        return embeddings

    def get_query_embedding(self, query: str, model_name: str = None) -> List[float]:
        """Encodes a single query (no caching for search queries to save space)."""
        model_name = model_name or settings.DEFAULT_EMBEDDING_MODEL
        self._load_model(model_name)
        emb = self.model.encode(query, show_progress_bar=False, convert_to_numpy=True)
        return emb.tolist()

# Singleton embeddings pipeline
embeddings_pipeline = EmbeddingsPipeline()
