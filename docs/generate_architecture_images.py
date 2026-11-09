import os
from pathlib import Path
import pymupdf

SVG_CONTENT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1260" width="1000" height="1260">
  <defs>
    <style>
      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 26px; font-weight: 800; fill: #F8FAFC; letter-spacing: -0.5px; }
      .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 500; fill: #94A3B8; }
      .container-title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 700; fill: #E2E8F0; }
      .node-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #FFFFFF; text-anchor: middle; dominant-baseline: middle; }
      .node-subtext { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 400; fill: #CBD5E1; text-anchor: middle; dominant-baseline: middle; }
      .edge-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 600; fill: #94A3B8; text-anchor: middle; }
      .badge-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 10px; font-weight: 700; fill: #FFFFFF; text-anchor: middle; dominant-baseline: middle; }
    </style>

    <!-- Gradients -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0B0F19" />
      <stop offset="100%" stop-color="#111827" />
    </linearGradient>

    <linearGradient id="indigoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6366F1" />
      <stop offset="100%" stop-color="#4F46E5" />
    </linearGradient>

    <linearGradient id="amberGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#F59E0B" />
      <stop offset="100%" stop-color="#D97706" />
    </linearGradient>

    <linearGradient id="emeraldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10B981" />
      <stop offset="100%" stop-color="#059669" />
    </linearGradient>

    <linearGradient id="purpleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8B5CF6" />
      <stop offset="100%" stop-color="#6D28D9" />
    </linearGradient>

    <!-- Drop Shadows -->
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.35" />
    </filter>

    <filter id="glowIndigo" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>

    <!-- Arrow Markers -->
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10B981" />
    </marker>
    <marker id="arrow-amber" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#F59E0B" />
    </marker>
  </defs>

  <!-- Background -->
  <rect width="1000" height="1260" rx="20" fill="url(#bgGrad)" />
  <rect width="996" height="1256" x="2" y="2" rx="18" fill="none" stroke="#1E293B" stroke-width="2" />

  <!-- Header -->
  <g transform="translate(50, 48)">
    <circle cx="20" cy="20" r="18" fill="#4F46E5" />
    <text x="20" y="21" font-size="20" text-anchor="middle" dominant-baseline="middle">💡</text>
    <text x="50" y="16" class="title">Lumina AI — System Architecture</text>
    <text x="50" y="38" class="subtitle">Dual-Stream TeX-RAG &amp; 5D Reproducibility Evaluation Engine</text>
  </g>

  <!-- ==================== CONTAINER 1: INGESTION PIPELINE ==================== -->
  <g transform="translate(40, 110)">
    <!-- Container Box -->
    <rect width="920" height="540" rx="16" fill="#0F172A" stroke="#334155" stroke-width="1.5" />
    <rect width="920" height="42" rx="16" fill="#1E293B" />
    <rect width="920" height="20" y="22" fill="#1E293B" />
    <text x="24" y="27" class="container-title">📄 1. Ingestion Pipeline (Dual-Stream TeX-RAG)</text>

    <!-- Node: Research Paper PDF -->
    <g transform="translate(330, 60)" filter="url(#shadow)">
      <rect width="260" height="50" rx="10" fill="url(#indigoGrad)" />
      <text x="130" y="25" class="node-text">📄 Research Paper PDF</text>
    </g>

    <!-- Arrow to Splitter -->
    <line x1="460" y1="110" x2="460" y2="135" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Node: Splitter -->
    <g transform="translate(365, 137)">
      <rect width="190" height="38" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1.5" />
      <text x="95" y="19" class="node-text">Dual-Stream Splitter</text>
    </g>

    <!-- Stream A Branch (Left) -->
    <path d="M 410 175 L 410 200 L 230 200 L 230 220" fill="none" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />
    <text x="245" y="193" class="edge-label">Stream A: Narrative &amp; Math</text>

    <!-- Stream B Branch (Right) -->
    <path d="M 510 175 L 510 200 L 690 200 L 690 220" fill="none" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />
    <text x="675" y="193" class="edge-label">Stream B: Structured Tables</text>

    <!-- Stream A Nodes -->
    <g transform="translate(90, 222)" filter="url(#shadow)">
      <rect width="280" height="48" rx="8" fill="#1E293B" stroke="#3B82F6" stroke-width="1.5" />
      <text x="140" y="24" class="node-text">PyMuPDF + LaTeX Normalizer</text>
    </g>
    <line x1="230" y1="270" x2="230" y2="292" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />
    <g transform="translate(90, 294)" filter="url(#shadow)">
      <rect width="280" height="48" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1.5" />
      <text x="140" y="18" class="node-text">Recursive Chunker</text>
      <text x="140" y="34" class="node-subtext">400 tokens / 60 token overlap</text>
    </g>

    <!-- Stream B Nodes (Novelty 4) -->
    <g transform="translate(550, 222)" filter="url(#shadow)">
      <rect width="280" height="48" rx="8" fill="url(#amberGrad)" />
      <text x="140" y="18" class="node-text">pdfplumber Table Extractor</text>
      <text x="140" y="34" class="node-subtext">Layout &amp; Boundary Analysis</text>
      <!-- Badge Novelty 4 -->
      <g transform="translate(205, -10)">
        <rect width="75" height="18" rx="9" fill="#B45309" stroke="#FDE68A" stroke-width="1" />
        <text x="37" y="10" class="badge-text">NOVELTY 4</text>
      </g>
    </g>
    <line x1="690" y1="270" x2="690" y2="292" stroke="#F59E0B" stroke-width="2" marker-end="url(#arrow-amber)" />
    <g transform="translate(550, 294)" filter="url(#shadow)">
      <rect width="280" height="48" rx="8" fill="url(#amberGrad)" />
      <text x="140" y="18" class="node-text">Markdown &amp; JSON Matrices</text>
      <text x="140" y="34" class="node-subtext">Captions + Headers + 2D Coordinates</text>
    </g>

    <!-- Merging to Embeddings -->
    <path d="M 230 342 L 230 375 L 410 375 L 410 395" fill="none" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />
    <path d="M 690 342 L 690 375 L 510 375 L 510 395" fill="none" stroke="#F59E0B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Jina Embeddings Node -->
    <g transform="translate(320, 397)" filter="url(#shadow)">
      <rect width="280" height="48" rx="8" fill="#1E293B" stroke="#6366F1" stroke-width="1.5" />
      <text x="140" y="18" class="node-text">Jina AI Embeddings v3</text>
      <text x="140" y="34" class="node-subtext">1024-dimensional semantic vectors</text>
    </g>

    <line x1="460" y1="445" x2="460" y2="470" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Qdrant Vector Store Node -->
    <g transform="translate(290, 472)" filter="url(#shadow)">
      <rect width="340" height="52" rx="10" fill="url(#emeraldGrad)" />
      <text x="170" y="20" class="node-text">🗄️ Qdrant Vector Database</text>
      <text x="170" y="37" class="node-subtext">Collections: lumina_papers &amp; lumina_tables</text>
    </g>
  </g>

  <!-- Connection Bridge Between Pipelines -->
  <line x1="500" y1="650" x2="500" y2="690" stroke="#10B981" stroke-width="2.5" stroke-dasharray="6,4" marker-end="url(#arrow-green)" />
  <rect x="440" y="662" width="120" height="20" rx="5" fill="#0F172A" stroke="#334155" stroke-width="1" />
  <text x="500" y="675" class="edge-label" fill="#10B981">Vector Index Sync</text>

  <!-- ==================== CONTAINER 2: QUERY & EVALUATION PIPELINE ==================== -->
  <g transform="translate(40, 700)">
    <!-- Container Box -->
    <rect width="920" height="510" rx="16" fill="#0F172A" stroke="#334155" stroke-width="1.5" />
    <rect width="920" height="42" rx="16" fill="#1E293B" />
    <rect width="920" height="20" y="22" fill="#1E293B" />
    <text x="24" y="27" class="container-title">🔍 2. Query &amp; Evaluation Pipeline</text>

    <!-- Node: User Query / Audit Request -->
    <g transform="translate(300, 60)" filter="url(#shadow)">
      <rect width="320" height="48" rx="10" fill="url(#indigoGrad)" />
      <text x="160" y="24" class="node-text">💬 User Question / Audit Request</text>
    </g>

    <line x1="460" y1="108" x2="460" y2="130" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Node: Vector Similarity Search -->
    <g transform="translate(320, 132)">
      <rect width="280" height="44" rx="8" fill="#1E293B" stroke="#475569" stroke-width="1.5" />
      <text x="140" y="16" class="node-text">Hybrid Vector Search</text>
      <text x="140" y="32" class="node-subtext">Cosine similarity + paper filters</text>
    </g>

    <line x1="460" y1="176" x2="460" y2="200" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Node: Context Assembly & Citations -->
    <g transform="translate(290, 202)">
      <rect width="340" height="46" rx="8" fill="#1E293B" stroke="#3B82F6" stroke-width="1.5" />
      <text x="170" y="17" class="node-text">Context Assembly &amp; Citation Anchors</text>
      <text x="170" y="33" class="node-subtext">Numbered text chunks [1] + Markdown tables</text>
    </g>

    <line x1="460" y1="248" x2="460" y2="272" stroke="#64748B" stroke-width="2" marker-end="url(#arrow)" />

    <!-- Node: LLM Reasoning -->
    <g transform="translate(270, 274)" filter="url(#shadow)">
      <rect width="380" height="52" rx="10" fill="url(#purpleGrad)" />
      <text x="190" y="20" class="node-text">🧠 Groq LLaMA 3.3 70B / Google Gemini</text>
      <text x="190" y="38" class="node-subtext">Strict zero-hallucination prompt constraints</text>
    </g>

    <!-- Output Split Branches -->
    <path d="M 400 326 L 400 360 L 240 360 L 240 380" fill="none" stroke="#10B981" stroke-width="2" marker-end="url(#arrow-green)" />
    <path d="M 520 326 L 520 360 L 680 360 L 680 380" fill="none" stroke="#F59E0B" stroke-width="2" marker-end="url(#arrow-amber)" />

    <!-- Output 1: Grounded QA -->
    <g transform="translate(70, 382)" filter="url(#shadow)">
      <rect width="340" height="85" rx="10" fill="url(#emeraldGrad)" />
      <text x="170" y="28" class="node-text">Grounded Answers &amp; Streaming</text>
      <text x="170" y="48" class="node-subtext">Page-level citations [1][2]</text>
      <text x="170" y="65" class="node-subtext">Cell-level table citations &amp; KaTeX formulas</text>
    </g>

    <!-- Output 2: Reproducibility Scorecard (Novelty 2) -->
    <g transform="translate(510, 382)" filter="url(#shadow)">
      <rect width="340" height="85" rx="10" fill="url(#amberGrad)" />
      <text x="170" y="25" class="node-text">5D Reproducibility Scorecard</text>
      <text x="170" y="44" class="node-subtext">ReproScore (0-100%) &amp; Letter Grade (A+ to F)</text>
      <text x="170" y="62" class="node-subtext">Runnable Reproduction Recipe &amp; Reviewer Export</text>
      <!-- Badge Novelty 2 -->
      <g transform="translate(255, -10)">
        <rect width="75" height="18" rx="9" fill="#B45309" stroke="#FDE68A" stroke-width="1" />
        <text x="37" y="10" class="badge-text">NOVELTY 2</text>
      </g>
    </g>
  </g>
</svg>
'''

def main():
    base_dir = Path("d:/LUMINA AI")
    docs_dir = base_dir / "docs"
    img_dir = base_dir / "frontend/static/img"
    docs_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    svg_file = docs_dir / "lumina_architecture.svg"
    svg_img_file = img_dir / "lumina_architecture.svg"
    svg_file.write_text(SVG_CONTENT, encoding="utf-8")
    svg_img_file.write_text(SVG_CONTENT, encoding="utf-8")
    print(f"Saved SVG to {svg_file} and {svg_img_file}")

    # Render PNG using PyMuPDF at 2x resolution (2000 x 2520 px)
    doc = pymupdf.open(stream=SVG_CONTENT.encode("utf-8"), filetype="svg")
    page = doc[0]
    mat = pymupdf.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    png_file = docs_dir / "lumina_architecture.png"
    png_img_file = img_dir / "lumina_architecture.png"
    pix.save(str(png_file))
    pix.save(str(png_img_file))
    print(f"Saved PNG to {png_file} and {png_img_file} (Dimensions: {pix.width}x{pix.height})")

    # Also save to artifact directory
    artifact_dir = Path("C:/Users/Lokesh Vardhan/.gemini/antigravity/brain/bad20ce7-b90e-457b-8916-ad83c273d692")
    if artifact_dir.exists():
        artifact_png = artifact_dir / "lumina_architecture.png"
        artifact_svg = artifact_dir / "lumina_architecture.svg"
        pix.save(str(artifact_png))
        artifact_svg.write_text(SVG_CONTENT, encoding="utf-8")
        print(f"Copied to artifact directory: {artifact_png}")

if __name__ == "__main__":
    main()
