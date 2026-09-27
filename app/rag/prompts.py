"""Prompt augmentation: system prompts, prompt templates and context injection."""
from typing import Any

from app.config import settings
from app.rag.chunker import count_tokens

NOT_FOUND_ANSWER = "I don't know - the uploaded papers do not contain enough information to answer that."

# System prompt: grounded generation, answer only from the retrieved context.
QA_SYSTEM_PROMPT = f"""You are Lumina, an AI research assistant.
Answer only using the provided context from the user's research papers.
Cite the supporting context after each claim using its number in square brackets, e.g. [1] or [2][3].
Be concise and precise. Use Markdown for lists or tables when it helps.
If the answer is not available in the context, reply exactly: "{NOT_FOUND_ANSWER}"
"""

QA_TEMPLATE = """Context:
{context}

Question:
{question}

Answer:"""

GROUNDED_TASK_SYSTEM_PROMPT = """You are Lumina, an AI research assistant.
Use only the provided context from the user's research papers. Do not invent facts, numbers or citations.
If the context does not cover something, say so instead of guessing."""


def format_context(chunks: list[dict[str, Any]], budget_tokens: int = settings.CONTEXT_TOKEN_BUDGET) -> tuple[str, list[dict[str, Any]]]:
    """Context injection: number each retrieved chunk with its source metadata.

    Returns the formatted context and the chunks that fit into the token budget.
    """
    blocks, used, total = [], [], 0
    for chunk in chunks:
        header = f"[{len(used) + 1}] {chunk['paper_name']} | page {chunk['page']} | {chunk.get('section') or 'Unknown section'}"
        block = f"{header}\n{chunk['text'].strip()}"
        cost = count_tokens(block)
        if used and total + cost > budget_tokens:
            break
        blocks.append(block)
        used.append(chunk)
        total += cost
    return "\n\n---\n\n".join(blocks), used


def build_qa_prompt(question: str, chunks: list[dict[str, Any]]) -> tuple[str, str, list[dict[str, Any]]]:
    context, used = format_context(chunks)
    return QA_SYSTEM_PROMPT, QA_TEMPLATE.format(context=context, question=question), used


SUMMARY_STYLES: dict[str, dict[str, str]] = {
    "abstract": {
        "query": "main problem, proposed approach, key contributions and results of the paper",
        "instruction": "Write a concise abstract-style summary (150-220 words): problem, approach, key results, significance.",
    },
    "methodology": {
        "query": "methodology, proposed method, model architecture, algorithm, experimental setup, datasets",
        "instruction": "Summarize the methodology: approach, architecture/algorithm, datasets and experimental setup. Use short sections.",
    },
    "results": {
        "query": "experimental results, evaluation metrics, performance, comparison with baselines, ablation",
        "instruction": "Summarize the results: key metrics and numbers, comparisons with baselines, and what they show.",
    },
    "conclusion": {
        "query": "conclusion, limitations, future work, implications",
        "instruction": "Summarize the conclusions, stated limitations and future work.",
    },
    "beginner": {
        "query": "main idea and problem the paper solves, simple explanation of the approach and results",
        "instruction": "Explain the paper to a beginner (ELI5): plain language, an everyday analogy, no jargon without a definition.",
    },
    "technical": {
        "query": "technical details, equations, architecture, training procedure, hyperparameters, results",
        "instruction": "Write a dense technical summary for an expert: methods, formulation, implementation details, quantitative results.",
    },
    "bullet": {
        "query": "key contributions, method, results and conclusions",
        "instruction": "Summarize as 8-12 crisp Markdown bullet points covering problem, method, results and takeaways.",
    },
    "one-page": {
        "query": "problem, motivation, method, datasets, results, limitations and conclusions",
        "instruction": "Write a one-page brief with headings: Problem, Approach, Key Results, Limitations, Takeaways.",
    },
}

SUMMARY_TEMPLATE = """Paper: {title}

Context:
{context}

Task:
{instruction}
Write the summary in Markdown."""

QUIZ_TEMPLATE = """Context:
{context}

Task:
Create {count} {difficulty} {kind} questions that test understanding of the context above.
{format_hint}
Return JSON only, shaped as: {{"questions": [{{"question": "...", "options": [...], "answer": "...", "explanation": "..."}}]}}"""

QUIZ_FORMATS = {
    "mcq": 'multiple-choice. Give exactly 4 options as full text; "answer" must be exactly one of the options.',
    "true_false": 'true/false. "options" must be ["True", "False"] and "answer" one of them.',
    "short_answer": 'short-answer. "options" must be null; "answer" is a short phrase of 1-5 words.',
}

FLASHCARD_TEMPLATE = """Context:
{context}

Task:
Create {count} study flashcards covering the most important concepts, terms, methods and findings in the context.
Return JSON only, shaped as: {{"cards": [{{"front": "term or question", "back": "definition or answer", "explanation": "optional extra detail"}}]}}"""

COMPARE_TEMPLATE = """Context (excerpts grouped by paper):
{context}

Task:
Compare these papers: {titles}.
1. A Markdown table with one column per paper and rows: Problem, Approach, Datasets, Key Results, Strengths, Limitations.
2. A short "Key Differences" section and a "Which to read for what" section.
Write "Not stated" where the context does not say. Do not add bracketed citation numbers."""

GAPS_TEMPLATE = """Context (excerpts grouped by paper):
{context}

Task:
Act as a peer reviewer. Identify research gaps across these papers: stated limitations, missing experiments,
untested assumptions, contradictions between papers, and promising future directions.
Return JSON only, shaped as:
{{"gaps": [{{"title": "...", "description": "...", "category": "limitation|missing_experiment|contradiction|future_work",
"papers": ["paper title", ...], "confidence": "high|medium|low", "suggestion": "how to address it"}}]}}"""
