import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "PaperMind AI"
    DEBUG: bool = False
    
    # Path Configurations
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    CACHE_DIR: Path = BASE_DIR / "cache"
    LOG_DIR: Path = BASE_DIR / "logs"
    DATABASE_DIR: Path = BASE_DIR / "database"
    
    # Database Settings
    DATABASE_PATH: Path = BASE_DIR / "database" / "papermind.db"
    
    # RAG Chunking Parameters
    CHUNK_SIZE: int = 700  # Target size in tokens (between 500 and 900)
    CHUNK_OVERLAP: int = 100  # Overlap in tokens (between 80 and 120)
    
    # Embeddings Configurations
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    AVAILABLE_EMBEDDING_MODELS: dict = {
        "BAAI/bge-small-en-v1.5": "BGE Small English (Fast, 384d)",
        "BAAI/bge-base-en-v1.5": "BGE Base English (Balanced, 768d)",
        "sentence-transformers/all-MiniLM-L6-v2": "MiniLM L6 (Ultralight, 384d)",
        "intfloat/e5-small-v2": "E5 Small V2 (Efficient, 384d)",
        "intfloat/e5-base-v2": "E5 Base V2 (High quality, 768d)"
    }
    
    # Re-ranking Configurations
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    USE_RERANKER: bool = True
    
    # Vector Database Settings
    DEFAULT_VECTOR_DB: str = "faiss"  # Choices: 'faiss', 'chroma'
    VECTOR_DB_DIR: Path = BASE_DIR / "cache" / "vector_stores"
    
    # Retrieval Settings
    TOP_K_DENSE: int = 5
    TOP_K_SPARSE: int = 5
    HYBRID_ALPHA: float = 0.5  # Fusion weight (0.0 = pure BM25, 1.0 = pure dense)
    RERANK_TOP_N: int = 3
    
    # Local LLM Configurations (Ollama)
    OLLAMA_API_BASE: str = "http://localhost:11434"
    DEFAULT_LLM_MODEL: str = "llama3.2"  # Alternatives: qwen2.5, gemma2, mistral
    LLM_TEMPERATURE: float = 0.0  # Keep low to avoid hallucination
    LLM_MAX_TOKENS: int = 1024
    
    # UI / Security Settings
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set = {"pdf"}
    
    # Settings configuration
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def create_directories(self):
        """Create standard application folders if they do not exist."""
        for directory in [self.UPLOAD_DIR, self.CACHE_DIR, self.LOG_DIR, self.DATABASE_DIR, self.VECTOR_DB_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

# Instantiate the settings singleton
settings = Settings()
settings.create_directories()
