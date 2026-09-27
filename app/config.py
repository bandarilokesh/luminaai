from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Lumina AI"
    DEBUG: bool = False

    # Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"
    MAX_UPLOAD_SIZE_MB: int = 50

    # LLM: "groq" or "gemini" (both called through their OpenAI-compatible endpoints)
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-lite-latest"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 2048

    # Embedding model (Jina AI API)
    JINA_API_KEY: str = ""
    EMBEDDING_MODEL: str = "jina-embeddings-v3"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_URL: str = "https://api.jina.ai/v1/embeddings"
    EMBEDDING_BATCH_SIZE: int = 32

    # Vector database (Qdrant). Use QDRANT_URL=":memory:" for an in-process store (tests).
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "lumina_papers"

    # Chunking (sizes in tokens; common chunk size is 200-500 with 10-20% overlap)
    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 60

    # Retrieval
    TOP_K: int = 5
    SCORE_THRESHOLD: float = 0.0
    CONTEXT_TOKEN_BUDGET: int = 6000

    # Observability (Langfuse). Tracing is disabled when keys are blank.
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    # Optional shared access code. Leave blank to keep the app open.
    ACCESS_CODE: str = ""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def DATABASE_PATH(self) -> Path:
        return self.DATA_DIR / "lumina.db"

    @property
    def LOG_DIR(self) -> Path:
        return self.DATA_DIR / "logs"

    @property
    def llm_model(self) -> str:
        return self.GEMINI_MODEL if self.LLM_PROVIDER.lower() == "gemini" else self.GROQ_MODEL

    def create_directories(self) -> None:
        for directory in (self.UPLOAD_DIR, self.DATA_DIR, self.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.create_directories()
