from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- General System Status ---
class SystemStatusResponse(BaseModel):
    app_name: str
    debug: bool
    gpu_available: bool
    gpu_device_name: Optional[str] = None
    provider_status: str
    current_model: str
    total_papers: int
    db_size_bytes: int

# --- Paper Metadata Schemas ---
class PaperResponse(BaseModel):
    id: str
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[str] = None
    doi: Optional[str] = None
    publication_year: Optional[int] = None
    file_path: str
    file_size: int
    uploaded_at: str
    status: str
    error_message: Optional[str] = None

class SimpleMessageResponse(BaseModel):
    message: str
    success: bool

# --- Search History Schemas ---
class SearchHistoryResponse(BaseModel):
    id: int
    query: str
    timestamp: str

# --- RAG / Retrieval / QA Schemas ---
class CitationItem(BaseModel):
    paper_name: str
    page: int
    section: Optional[str] = None
    chunk_id: str
    text_snippet: str

class QARequest(BaseModel):
    paper_ids: List[str] = Field(..., description="List of paper IDs to search. Empty list searches across all papers.")
    question: str = Field(..., min_length=1, description="Question asked by the user.")
    llm_model: Optional[str] = Field(None, description="Specify LLM model. Defaults to settings default.")
    use_hybrid: bool = Field(True, description="Enable hybrid sparse/dense retrieval.")
    use_reranker: bool = Field(True, description="Enable cross-encoder re-ranking.")

class QAResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    confidence_score: float
    retrieved_chunk_ids: List[str]
    latency_sec: float

# --- Summarization Schemas ---
class SummaryRequest(BaseModel):
    paper_id: str
    summary_type: str = Field("abstract", description="Type of summary (abstract, methodology, results, conclusion, beginner, technical, bullet, one-page)")
    llm_model: Optional[str] = None

class SummaryResponse(BaseModel):
    paper_id: str
    summary_type: str
    summary_text: str
    latency_sec: float

# --- Quiz & Flashcard Schemas ---
class QuizItem(BaseModel):
    question: str
    options: Optional[List[str]] = Field(None, description="Options for MCQs (e.g. A, B, C, D)")
    answer: str = Field(..., description="Correct answer")
    explanation: Optional[str] = Field(None, description="Explanation why the answer is correct")

class QuizRequest(BaseModel):
    paper_ids: List[str]
    quiz_type: str = Field("mcq", description="mcq, true_false, short_answer, long_answer")
    difficulty: str = Field("medium", description="easy, medium, hard")
    num_questions: int = Field(5, ge=1, le=20)

class QuizResponse(BaseModel):
    quiz_type: str
    difficulty: str
    questions: List[QuizItem]
    latency_sec: float

class FlashcardItem(BaseModel):
    front: str = Field(..., description="Concept, term or question")
    back: str = Field(..., description="Definition, explanation or answer")
    explanation: Optional[str] = None

class FlashcardRequest(BaseModel):
    paper_ids: List[str]
    num_cards: int = Field(5, ge=1, le=20)

class FlashcardResponse(BaseModel):
    cards: List[FlashcardItem]
    latency_sec: float

# --- Dashboard Stats schemas ---
class DashboardStatsResponse(BaseModel):
    total_papers: int
    questions_asked: int
    summaries_generated: int
    study_sessions: int

class ActivityItem(BaseModel):
    event_type: str = Field(..., description="Type of activity: upload, qa, summary")
    description: str
    timestamp: str
    paper_id: Optional[str] = None

class ActivityResponse(BaseModel):
    activities: List[ActivityItem]

# --- Research Gap schemas ---
class ResearchGapResponse(BaseModel):
    gaps: List[Dict[str, Any]] = Field(..., description="Identified limitations, conflicts, future work and opportunities")
    latency_sec: float
