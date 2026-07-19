from typing import List, Dict, Any, Tuple

# --- System QA Prompt ---
QA_SYSTEM_PROMPT = """You are a highly precise, expert AI Software Architect and Research Scientist assisting in analyzing research papers.
Your task is to answer the user's question strictly using the provided context blocks.

INSTRUCTIONS:
1. Base your answer solely on the retrieved context below. Do NOT invent, assume, or extrapolate any information.
2. If the context does not contain sufficient evidence to answer the question, reply EXACTLY with:
   "I cannot find sufficient evidence in the uploaded paper."
3. Cite the source block for each factual claim using the format [Block X].
4. Keep the answer structured, professional, and technical.
5. FORMATTING: Output ONLY clean plain text. Do NOT use any Markdown formatting whatsoever. No hashtags (#), no asterisks (*), no bold/italic markers, no table pipes (|), no horizontal rules (---), no backticks, no bullet symbols. Use plain numbered lists (1. 2. 3.) or simple dashes (-) for lists if needed.

SELF-ASSESSMENT (Self-RAG):
For every claim you make, you must ensure it is either:
- [SUPPORTED]: Directly stated in the context blocks.
- [INFERRED]: Logically follows from the context blocks.
Do NOT include any claims that are [UNSUPPORTED] (not found in context).
"""

QA_USER_TEMPLATE = """CONTEXT BLOCKS:
{context_blocks}

QUESTION:
{question}

Factual, citation-aware answer:"""

# --- Summarization Templates ---
SUMMARY_PROMPTS = {
    "abstract": """You are an expert Research Scientist. Generate a concise, high-level summary of the Abstract of this research paper.
Describe the core problem, the proposed solution, and main findings. Keep it under 250 words.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "methodology": """Analyze the research methodology from the text. Summarize the experiments, algorithms, datasets, math equations, and training processes used by the authors.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "results": """Analyze the results and discussion from the text. Summarize the main metrics achieved, baseline comparisons, figures/tables descriptions (if mentioned), and performance gains.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "conclusion": """Summarize the conclusion of the paper. Highlight the contributions, limitations acknowledged by the authors, and future research directions.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "beginner": """Explain this paper to a beginner (ELI5 style). Avoid dense academic jargon. Use analogies and simple language to explain the core contribution, why it matters, and what the authors achieved.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "technical": """Generate an in-depth, rigorous technical brief of this paper. Detail the mathematical formulations, architecture parameters, optimizers, learning rates, loss functions, and exact hardware specs if mentioned.
FORMATTING: Output ONLY clean plain text. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "bullet": """Create a bulleted summary highlighting the key takeaways from this paper:
- Key Problem
- Core Novelty / Contribution
- Key Methodology Details
- Key Results & Metrics
- Notable Future Work
FORMATTING: Output ONLY clean plain text. Use simple dashes (-) for bullet points. No Markdown, no hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}""",

    "one-page": """Generate a comprehensive one-page executive brief of the paper. Include sections for Overview, Key Methods, Results, and Analysis.
FORMATTING: Output ONLY clean plain text. Use simple section labels (e.g. "Overview:") instead of Markdown headings. No hashtags (#), no asterisks (*), no bold/italic, no tables, no horizontal rules (---), no backticks.
PAPER TEXT:
{text}"""
}

# --- Study Tools & Extractions ---
QUIZ_GENERATOR_PROMPT = """You are an academic test designer. Create a {difficulty} difficulty quiz in {quiz_type} format containing exactly {num_questions} questions from the research paper content below.

FORMAT REQUIREMENTS:
Return your response ONLY as a valid JSON array of objects. Do not include any markdown fences (like ```json), commentary, or leading/trailing text.
Each object must contain the following fields:
- "question": string (the test question)
- "options": list of strings (4 options for MCQ, or ["True", "False"] for True/False quiz. Omit for short_answer)
- "answer": string (the correct option or short answer text)
- "explanation": string (why this is the correct answer based on the paper)

PAPER TEXT:
{text}

JSON Output:"""

FLASHCARD_GENERATOR_PROMPT = """Extract exactly {num_cards} key terms, concepts, architectures, or formulas from the paper text below to generate study flashcards.

FORMAT REQUIREMENTS:
Return your response ONLY as a valid JSON array of objects. Do not include any markdown fences (like ```json), commentary, or leading/trailing text.
Each object must contain:
- "front": string (the concept name, term, or question)
- "back": string (the definition, explanation, or answer)
- "explanation": string (additional context or formula details)

PAPER TEXT:
{text}

JSON Output:"""

GAP_DETECTOR_PROMPT = """Analyze the research paper text below to identify potential research gaps, limitations, conflicts, or future work opportunities.

Look for:
1. Missing experiments (e.g. not tested on specific datasets, domains, or scales).
2. Future work suggested by the authors.
3. Open problems or conflicting conclusions.
4. Novel research opportunities arising from this work.

FORMAT REQUIREMENTS:
Return your response ONLY as a valid JSON array of objects. Do not include any markdown fences (like ```json), commentary, or leading/trailing text.
Each object must contain:
- "section": string (which paper section or context this relates to, e.g. "Experiments", "Future Work")
- "gap_description": string (detailed description of the research gap or limitation)
- "confidence": string ("high", "medium", or "low" based on how explicitly this gap is supported by the text)

PAPER TEXT:
{text}

JSON Output:"""

def build_qa_prompt(question: str, citations: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Builds the system and user prompt for RAG QA."""
    context_blocks = ""
    for idx, c in enumerate(citations):
        context_blocks += (
            f"--- BLOCK {idx+1} | Source: \"{c['paper_name']}\" | Page: {c['page']} | Section: {c['section']} ---\n"
            f"{c['text_snippet']}\n\n"
        )
        
    user_prompt = QA_USER_TEMPLATE.format(
        context_blocks=context_blocks.strip(),
        question=question
    )
    return QA_SYSTEM_PROMPT, user_prompt
