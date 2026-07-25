from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "Lumina Ai"
    DEBUG: bool = False
    
    # Path Configurations
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    CACHE_DIR: Path = BASE_DIR / "cache"
    LOG_DIR: Path = BASE_DIR / "logs"
    DATABASE_DIR: Path = BASE_DIR / "database"
    
    # Database Settings
    DATABASE_PATH: Path = BASE_DIR / "database" / "lumina_ai.db"
    
    # RAG Chunking Parameters
    CHUNK_SIZE: int = 700  # Target size in tokens (between 500 and 900)
    CHUNK_OVERLAP: int = 100  # Overlap in tokens (between 80 and 120)
    
    # Embeddings Configurations
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"

    # Re-ranking Configurations
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    USE_RERANKER: bool = True
    
    # Vector Database Settings
    DEFAULT_VECTOR_DB: str = "faiss"  # Choices: 'faiss', 'chroma'
    VECTOR_DB_DIR: Path = BASE_DIR / "cache" / "vector_stores"
    
    # Retrieval Settings
    TOP_K_DENSE: int = 5
    RERANK_TOP_N: int = 3
    
    # Gemini API Configurations
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"
    MODEL_NAME: str = "gemini-flash-lite-latest"
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 1024
    
    # Ollama Configurations
    OLLAMA_API_URL: str = "http://localhost:11434"
    
    # UI / Security Settings
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set = {"pdf"}

    # Optional shared access code. Leave blank to keep the app fully open.
    # When set, visitors must enter this code before using the app.
    ACCESS_CODE: str = ""
    
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
