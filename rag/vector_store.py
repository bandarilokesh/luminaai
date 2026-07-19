import json
import os
import shutil
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import faiss
import chromadb
import pickle
import re
from config.settings import settings
from utils.logger import logger
from rag.embeddings import embeddings_pipeline
from rank_bm25 import BM25Okapi

class VectorStoreManager:
    """Manages local vector store backends (FAISS & ChromaDB) under a unified interface."""
    def __init__(self, vector_db_dir: Path = settings.VECTOR_DB_DIR):
        self.vector_db_dir = vector_db_dir
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize FAISS and Chroma directories
        self.faiss_dir = self.vector_db_dir / "faiss"
        self.faiss_dir.mkdir(parents=True, exist_ok=True)
        
        self.chroma_dir = self.vector_db_dir / "chroma"
        self._chroma_client = None

        self.bm25_dir = self.vector_db_dir / "bm25"
        self.bm25_dir.mkdir(parents=True, exist_ok=True)

    def _tokenize_text(self, text: str) -> List[str]:
        """Simple alphanumeric tokenizer for BM25."""
        return re.findall(r'\b\w+\b', text.lower())

    def _save_bm25_index(self, paper_id: str, chunks: List[Dict[str, Any]]):
        """Build and save BM25 index for a paper."""
        try:
            corpus = [self._tokenize_text(c["text"]) for c in chunks]
            bm25 = BM25Okapi(corpus)
            bm25_file = self.bm25_dir / f"{paper_id}.pkl"
            with open(bm25_file, "wb") as f:
                pickle.dump(bm25, f)
            logger.info(f"BM25 index saved for paper: {paper_id}")
        except Exception as e:
            logger.error(f"Failed to save BM25 index for {paper_id}: {str(e)}")

    def load_bm25_index(self, paper_id: str) -> Optional[BM25Okapi]:
        """Load BM25 index for a paper."""
        bm25_file = self.bm25_dir / f"{paper_id}.pkl"
        if bm25_file.exists():
            try:
                with open(bm25_file, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Failed to load BM25 index for {paper_id}: {str(e)}")
        return None

    def _get_chroma_client(self) -> chromadb.PersistentClient:
        """Lazily initialize ChromaDB Persistent Client."""
        if self._chroma_client is None:
            logger.info(f"Initializing ChromaDB Persistent Client at: {self.chroma_dir}")
            self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_dir))
        return self._chroma_client

    def _get_chroma_collection(self) -> chromadb.Collection:
        """Get or create the unified papers collection in ChromaDB."""
        client = self._get_chroma_client()
        return client.get_or_create_collection(
            name="lumina_ai_chunks",
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )

    # --- FAISS CRUD Operations ---
    def _save_faiss_index(self, paper_id: str, index: faiss.Index, metadata: List[Dict[str, Any]]):
        """Save a single paper FAISS index and metadata to disk."""
        paper_dir = self.faiss_dir / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index binary
        index_file = paper_dir / "index.faiss"
        faiss.write_index(index, str(index_file))
        
        # Save metadata mapping as JSON
        metadata_file = paper_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        logger.info(f"FAISS index and metadata saved for paper: {paper_id}")

    def _load_faiss_index(self, paper_id: str) -> Optional[Tuple[faiss.Index, List[Dict[str, Any]]]]:
        """Load a single paper FAISS index and metadata from disk."""
        paper_dir = self.faiss_dir / paper_id
        index_file = paper_dir / "index.faiss"
        metadata_file = paper_dir / "metadata.json"
        
        if not index_file.exists() or not metadata_file.exists():
            return None
            
        index = faiss.read_index(str(index_file))
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        return index, metadata

    def index_chunks_faiss(self, paper_id: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> bool:
        """Create and write a FAISS index for the given chunks."""
        try:
            if not embeddings:
                return False
                
            dimension = len(embeddings[0])
            # Use IndexFlatIP (Inner Product) with normalized vectors for Cosine Similarity
            index = faiss.IndexFlatIP(dimension)
            
            # Normalize vectors
            np_embeddings = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(np_embeddings)
            
            # Add to index
            index.add(np_embeddings)
            
            # Prepare metadata mapping
            metadata_list = []
            for chunk in chunks:
                metadata_list.append({
                    "chunk_id": chunk["chunk_id"],
                    "paper_id": chunk["paper_id"],
                    "paper_name": chunk["paper_name"],
                    "text": chunk["text"],
                    "page": chunk["page"],
                    "section": chunk["section"],
                    "heading": chunk["heading"]
                })
                
            self._save_faiss_index(paper_id, index, metadata_list)
            return True
        except Exception as e:
            logger.error(f"Error indexing chunks in FAISS: {str(e)}", exc_info=True)
            return False

    # --- ChromaDB CRUD Operations ---
    def index_chunks_chroma(self, paper_id: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> bool:
        """Write chunks and embeddings to ChromaDB collection."""
        try:
            if not embeddings:
                return False
                
            collection = self._get_chroma_collection()
            
            ids = [chunk["chunk_id"] for chunk in chunks]
            texts = [chunk["text"] for chunk in chunks]
            
            metadatas = []
            for chunk in chunks:
                metadatas.append({
                    "paper_id": chunk["paper_id"],
                    "paper_name": chunk["paper_name"],
                    "page": chunk["page"],
                    "section": chunk["section"],
                    "heading": chunk["heading"]
                })
                
            # Add items to collection
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Indexed {len(chunks)} chunks in ChromaDB for paper: {paper_id}")
            return True
        except Exception as e:
            logger.error(f"Error indexing chunks in ChromaDB: {str(e)}", exc_info=True)
            return False

    # --- Unified Interfaces ---
    def index_paper_chunks(self, paper_id: str, chunks: List[Dict[str, Any]]) -> bool:
        """Runs embeddings generation and indexes them in the active Vector Database."""
        try:
            logger.info(f"Generating embeddings and indexing paper {paper_id} using backend {settings.DEFAULT_VECTOR_DB}...")
            
            # Extract texts for embeddings
            texts = [chunk["text"] for chunk in chunks]
            embeddings = embeddings_pipeline.get_embeddings(texts)
            
            if settings.DEFAULT_VECTOR_DB == "faiss":
                success = self.index_chunks_faiss(paper_id, chunks, embeddings)
            else:
                success = self.index_chunks_chroma(paper_id, chunks, embeddings)
                
            if success:
                self._save_bm25_index(paper_id, chunks)
                
            return success
                
        except Exception as e:
            logger.error(f"Failed unified vector indexing: {str(e)}", exc_info=True)
            return False

    def delete_paper_from_vector_store(self, paper_id: str) -> bool:
        """Deletes a paper from the active vector store index."""
        try:
            # 1. Clean FAISS directory
            paper_dir = self.faiss_dir / paper_id
            if paper_dir.exists():
                shutil.rmtree(paper_dir)
                logger.info(f"Deleted FAISS index files for paper: {paper_id}")
                
            # 2. Clean ChromaDB collection
            # To delete from chroma, we remove documents matching metadata filter
            if self._chroma_client is not None or self.chroma_dir.exists():
                collection = self._get_chroma_collection()
                collection.delete(where={"paper_id": paper_id})
                logger.info(f"Deleted ChromaDB records for paper: {paper_id}")
                
            # 3. Clean BM25 index
            bm25_file = self.bm25_dir / f"{paper_id}.pkl"
            if bm25_file.exists():
                bm25_file.unlink()
                logger.info(f"Deleted BM25 index for paper: {paper_id}")
                
            return True
        except Exception as e:
            logger.error(f"Error deleting vector store records: {str(e)}")
            return False

    def search_faiss(self, paper_ids: List[str], query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches across FAISS index files of selected papers, sorting and merging scores."""
        results = []
        
        # Load and search index for each paper
        for p_id in paper_ids:
            loaded = self._load_faiss_index(p_id)
            if not loaded:
                continue
            index, metadata = loaded
            
            # Search query
            np_query = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(np_query)
            
            # FAISS search
            scores, indices = index.search(np_query, min(top_k, index.ntotal))
            
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:
                    continue
                # Cosine Similarity is score (since vectors were normalized)
                # Map to [0,1] range (optional, FlatIP gives cosine similarity in [-1,1])
                results.append({
                    "metadata": metadata[idx],
                    "score": float(score)
                })
                
        # Sort combined results by similarity score descending, return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_chroma(self, paper_ids: List[str], query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches across ChromaDB collection with paper_id metadata filtering."""
        results = []
        collection = self._get_chroma_collection()
        
        # Construct filter
        where_filter = {}
        if len(paper_ids) == 1:
            where_filter = {"paper_id": paper_ids[0]}
        elif len(paper_ids) > 1:
            where_filter = {"paper_id": {"$in": paper_ids}}
            
        # ChromaDB query
        query_res = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter if paper_ids else None
        )
        
        # Parse Chroma response formats
        if query_res and query_res["ids"] and query_res["ids"][0]:
            ids = query_res["ids"][0]
            docs = query_res["documents"][0]
            metadatas = query_res["metadatas"][0]
            distances = query_res["distances"][0] # Cosine distance
            
            for i in range(len(ids)):
                # Convert cosine distance to cosine similarity: score = 1 - distance
                score = 1.0 - distances[i]
                
                # Merge document text inside metadata
                meta = metadatas[i].copy()
                meta["chunk_id"] = ids[i]
                meta["text"] = docs[i]
                
                results.append({
                    "metadata": meta,
                    "score": float(score)
                })
                
        return results

    def search(self, paper_ids: List[str], query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve top-k closest chunks matching query vector across selected papers."""
        if settings.DEFAULT_VECTOR_DB == "faiss":
            return self.search_faiss(paper_ids, query_vector, top_k)
        else:
            return self.search_chroma(paper_ids, query_vector, top_k)

# Singleton vector store manager
vector_store_manager = VectorStoreManager()
# Export base functions directly for easier integration
index_paper_chunks = vector_store_manager.index_paper_chunks
delete_paper_from_vector_store = vector_store_manager.delete_paper_from_vector_store
