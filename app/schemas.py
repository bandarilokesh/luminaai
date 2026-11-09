from pydantic import BaseModel, Field


class Paper(BaseModel):
    id: str
    title: str
    authors: str | None = ""
    abstract: str | None = ""
    file_name: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str
    error_message: str | None = None
    uploaded_at: str


class UploadUrlRequest(BaseModel):
    url: str
    filename: str | None = None


class Message(BaseModel):
    message: str
    success: bool = True


class Citation(BaseModel):
    paper_id: str
    paper_name: str
    page: int
    section: str | None = None
    chunk_id: str
    text_snippet: str
    score: float
    kind: str = "text"  # "text" chunk or "table"
    table_index: int | None = None


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    paper_ids: list[str] = Field(default_factory=list, description="Papers to search. Empty = all papers.")


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieval_score: float
    latency_sec: float
    trace_id: str | None = None


class SummaryRequest(BaseModel):
    paper_id: str
    summary_type: str = "abstract"
    refresh: bool = False


class SummaryResponse(BaseModel):
    paper_id: str
    summary_type: str
    summary_text: str
    cached: bool
    latency_sec: float


class QuizRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=1)
    quiz_type: str = "mcq"
    difficulty: str = Field("medium", pattern="^(easy|medium|hard)$")
    num_questions: int = Field(5, ge=1, le=15)


class QuizItem(BaseModel):
    question: str
    options: list[str] | None = None
    answer: str
    explanation: str | None = None


class QuizResponse(BaseModel):
    quiz_type: str
    difficulty: str
    questions: list[QuizItem]
    latency_sec: float


class FlashcardRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=1)
    num_cards: int = Field(8, ge=1, le=20)


class Flashcard(BaseModel):
    front: str
    back: str
    explanation: str | None = None


class FlashcardResponse(BaseModel):
    cards: list[Flashcard]
    latency_sec: float


class ResearchGap(BaseModel):
    title: str
    description: str
    category: str
    papers: list[str]
    confidence: str
    suggestion: str


class ResearchGapResponse(BaseModel):
    gaps: list[ResearchGap]
    latency_sec: float


class CompareResponse(BaseModel):
    comparison_markdown: str
    latency_sec: float


class Stats(BaseModel):
    total_papers: int
    questions_asked: int
    summaries_generated: int
    study_sessions: int


class Activity(BaseModel):
    event_type: str
    description: str
    paper_id: str | None = None
    timestamp: str


class ServiceStatus(BaseModel):
    name: str
    detail: str
    status: str  # "ok" | "warning" | "error"


class SystemStatus(BaseModel):
    app_name: str
    llm_provider: str
    llm_model: str
    embedding_model: str
    embedding_dim: int
    collection: str
    vectors_stored: int
    total_papers: int
    chunk_size: int
    chunk_overlap: int
    top_k: int
    tracing_enabled: bool
    services: list[ServiceStatus]


# --- Novelty 4: dual-stream tables ---
class TableItem(BaseModel):
    table_index: int
    page: int
    caption: str
    markdown: str
    headers: list[str]
    rows: list[list[str]]


class PaperTablesResponse(BaseModel):
    paper_id: str
    paper_title: str
    tables: list[TableItem]


# --- Novelty 2: reproducibility & leakage audit ---
class AuditItem(BaseModel):
    parameter: str
    status: str = Field(..., description="specified | missing | inferred | partial")
    value: str | None = None
    citation_page: int | None = None
    risk_level: str = Field("low", description="low | medium | high")
    note: str


class AuditCategory(BaseModel):
    key: str
    category_name: str
    score: float = Field(..., ge=0.0, le=100.0)
    weight: float
    items: list[AuditItem]


class LinkCheck(BaseModel):
    url: str
    live: bool | None = None
    status: str


class AuditSignals(BaseModel):
    repo_urls: list[str] = Field(default_factory=list)
    link_checks: list[LinkCheck] = Field(default_factory=list)
    accelerators: list[str] = Field(default_factory=list)
    seed_mentions: int = 0
    variance_mentions: int = 0


class ReproducibilityReport(BaseModel):
    paper_id: str
    paper_title: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: str
    classification: str
    categories: list[AuditCategory]
    missing_critical_parameters: list[str]
    potential_leakage_risks: list[str]
    reproduction_recipe: str
    recipe_command: str
    estimated_hardware: str
    signals: AuditSignals
    created_at: str
    cached: bool = False
    latency_sec: float = 0.0
