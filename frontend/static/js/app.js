/* ============================================================
   Lumina AI - single-page app controller
   ============================================================ */

const API_BASE = '/api';

// ---- API client: throws Error(detail) so callers can show the server's message ----
async function request(method, path, body, isForm = false) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
        if (isForm) opts.body = body;
        else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    }
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (res.status === 401) { window.location.reload(); throw new Error('Access code required.'); }
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : `${res.status} ${res.statusText}`);
    return data;
}

const api = {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
    del: (path) => request('DELETE', path),
    upload: (path, file) => { const fd = new FormData(); fd.append('file', file); return request('POST', path, fd, true); },
};

/** Run an API call; on failure show a toast and return null. */
async function attempt(promise) {
    try { return await promise; } catch (e) { showToast(e.message, 'error'); return null; }
}

// ---- State ----
const state = {
    currentPage: 'dashboard',
    selectedPapers: [],
    chatHistory: [],
    chatBusy: false,
    quizItems: null,
    userAnswers: {},
    quizSubmitted: false,
    flashcards: null,
    cardIndex: 0,
    cardFlipped: false,
    researchGaps: null,
    exports: {},          // latest summary / comparison markdown, keyed by name
    pollTimer: null,
};

// ---- Helpers ----
function showToast(message, type = 'info') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), type === 'error' ? 6000 : 3000);
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const diff = Math.floor((Date.now() - d) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** Render model Markdown safely; [n] citation markers become badges. */
function md(text) {
    if (!text) return '';
    let html = (window.marked && window.DOMPurify)
        ? DOMPurify.sanitize(marked.parse(text))
        : `<p style="white-space:pre-wrap;">${escapeHtml(text)}</p>`;
    return html.replace(/\[(\d{1,2})\]/g, '<sup class="cite">$1</sup>');
}

const spinner = () => '<div style="display:flex;justify-content:center;padding:40px;"><div class="spinner"></div></div>';
const errorBox = (msg) => `<p class="body-sm text-error" style="padding:24px 0;">${escapeHtml(msg)}</p>`;

function downloadAs(filename, content) {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown' }));
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

function exportMarkdown(key, filename) {
    if (state.exports[key]) downloadAs(filename, state.exports[key]);
}

function shortTitle(title, n = 38) {
    return escapeHtml(title.length > n ? title.substring(0, n) + '...' : title);
}

function paperChips(papers, emptyText = 'No indexed papers yet. Upload a PDF first.') {
    if (!papers.length) return `<p class="body-sm text-muted">${emptyText}</p>`;
    return papers.map(p => `
        <label class="chip ${state.selectedPapers.includes(p.id) ? 'chip-active' : 'chip-default'}" style="cursor:pointer;" title="${escapeHtml(p.title)}">
            <input type="checkbox" value="${p.id}" ${state.selectedPapers.includes(p.id) ? 'checked' : ''} style="display:none;" onchange="togglePaperSelection(this)" />
            ${shortTitle(p.title)}
        </label>`).join('');
}

function togglePaperSelection(checkbox) {
    const id = checkbox.value;
    state.selectedPapers = checkbox.checked
        ? [...new Set([...state.selectedPapers, id])]
        : state.selectedPapers.filter(p => p !== id);
    checkbox.parentElement.className = `chip ${checkbox.checked ? 'chip-active' : 'chip-default'}`;
}

async function readyPapers() {
    const papers = await attempt(api.get('/papers/')) || [];
    const ready = papers.filter(p => p.status === 'completed');
    const readyIds = new Set(ready.map(p => p.id));
    state.selectedPapers = state.selectedPapers.filter(id => readyIds.has(id));
    return ready;
}

// ---- Router ----
const PAGES = {
    dashboard: ['Dashboard', () => renderDashboard],
    library: ['Library', () => renderLibrary],
    upload: ['Upload Research', () => renderUpload],
    qa: ['Ask Your Papers', () => renderQA],
    summary: ['Summaries', () => renderSummary],
    'study-tools': ['Study Tools', () => renderStudyTools],
    'research-gaps': ['Research Gaps', () => renderResearchGaps],
    comparison: ['Paper Comparison', () => renderComparison],
    settings: ['Settings', () => renderSettings],
};

function navigate(page) {
    if (window.location.hash.replace('#', '') !== page) window.location.hash = page;
    else renderPage();
}

function updateActiveNav() {
    document.querySelectorAll('.nav-item, .mobile-nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === state.currentPage);
    });
}

function renderPage() {
    clearInterval(state.pollTimer);
    const container = document.getElementById('page-content');
    const page = PAGES[state.currentPage] ? state.currentPage : 'dashboard';
    state.currentPage = page;
    document.getElementById('topnav-title').textContent = PAGES[page][0];
    container.innerHTML = spinner();
    container.classList.remove('animate-fade-in');
    void container.offsetWidth;
    container.classList.add('animate-fade-in');
    updateActiveNav();
    if (window.innerWidth < 1024) document.body.classList.remove('sidebar-open');
    PAGES[page][1]()(container);
}

// ============================================================
// PAGE: Dashboard
// ============================================================
function serviceRows(services) {
    return services.map(s => `
        <div class="service-row">
            <span class="service-dot ${s.status}"></span>
            <div style="min-width:0;">
                <div class="label-md" style="color:var(--on-surface);">${escapeHtml(s.name)}</div>
                <div class="label-sm text-muted truncate" title="${escapeHtml(s.detail)}">${escapeHtml(s.detail)}</div>
            </div>
        </div>`).join('');
}

async function renderDashboard(el) {
    const [stats, activities, status] = await Promise.all([
        api.get('/stats').catch(() => null),
        api.get('/activity?limit=6').catch(() => []),
        api.get('/status').catch(() => null),
    ]);
    const s = stats || { total_papers: 0, questions_asked: 0, summaries_generated: 0, study_sessions: 0 };
    const icons = { upload: 'upload', indexed: 'database', qa: 'question_answer', summary: 'article', quiz: 'quiz', flashcards: 'style', compare: 'compare_arrows', gaps: 'troubleshoot' };

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-xl);">
        <section style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:var(--sp-md);">
            <div>
                <h2 class="headline-lg" style="margin-bottom:var(--sp-xs);">Welcome back.</h2>
                <p class="body-md text-muted">Upload papers, ask grounded questions, and study faster.</p>
            </div>
            <div style="display:flex;gap:var(--sp-sm);flex-wrap:wrap;">
                <button class="btn-primary" onclick="navigate('upload')"><span class="material-symbols-outlined" style="font-size:18px;">upload_file</span> Upload Paper</button>
                <button class="btn-secondary" onclick="navigate('qa')"><span class="material-symbols-outlined" style="font-size:18px;">contact_support</span> Ask a Question</button>
            </div>
        </section>

        <section class="grid-4">
            ${[['description', 'Papers', s.total_papers], ['psychology', 'Questions Asked', s.questions_asked],
               ['auto_awesome', 'Summaries', s.summaries_generated], ['school', 'Study Sessions', s.study_sessions]]
               .map(([icon, label, value]) => `
            <div class="academic-glass stat-card">
                <div class="stat-icon" style="color:var(--primary);"><span class="material-symbols-outlined">${icon}</span></div>
                <div class="stat-value">${value}</div>
                <div class="stat-label">${label}</div>
            </div>`).join('')}
        </section>

        <div class="dashboard-grid">
            <section>
                <h3 class="headline-md mb-md">System Status</h3>
                <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
                    ${status ? `<div class="service-grid">${serviceRows(status.services)}</div>`
                             : '<p class="body-sm text-error">Backend unreachable.</p>'}
                </div>
            </section>
            <section>
                <h3 class="headline-md mb-md">Recent Activity</h3>
                ${activities?.length ? `
                <div class="timeline">
                    ${activities.map(a => `
                    <div class="timeline-item">
                        <div class="timeline-dot ${a.event_type}"><span class="material-symbols-outlined">${icons[a.event_type] || 'bookmark'}</span></div>
                        <div style="min-width:0;">
                            <p class="label-md" style="color:var(--on-surface);overflow-wrap:anywhere;">${escapeHtml(a.description)}</p>
                            <p class="label-sm text-muted">${timeAgo(a.timestamp)}</p>
                        </div>
                    </div>`).join('')}
                </div>` : '<p class="body-sm text-muted">No activity yet. Upload a paper to get started.</p>'}
            </section>
        </div>
    </div>`;
}

// ============================================================
// PAGE: Library
// ============================================================
async function renderLibrary(el) {
    const papers = await attempt(api.get('/papers/'));
    if (!papers) { el.innerHTML = errorBox('Could not load the library.'); return; }
    const sort = state.librarySort || 'recent';
    const sorted = [...papers].sort((a, b) => sort === 'title' ? a.title.localeCompare(b.title) : b.uploaded_at.localeCompare(a.uploaded_at));

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <section style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
            <div style="position:relative;flex:1;min-width:200px;">
                <span class="material-symbols-outlined" style="position:absolute;left:16px;top:50%;transform:translateY(-50%);color:var(--on-surface-variant);font-size:18px;">search</span>
                <input class="form-input" id="lib-search" style="padding-left:44px;" placeholder="Search titles and authors..." />
            </div>
            <select class="form-select" id="lib-sort" style="width:auto;min-width:160px;">
                <option value="recent" ${sort === 'recent' ? 'selected' : ''}>Recently added</option>
                <option value="title" ${sort === 'title' ? 'selected' : ''}>Title</option>
            </select>
        </section>
        <div class="grid-cards" id="lib-grid">
            ${sorted.map(renderPaperCard).join('')}
            <div class="empty-state" onclick="navigate('upload')">
                <div class="empty-icon"><span class="material-symbols-outlined" style="font-size:32px;color:var(--primary);">add_notes</span></div>
                <h3 class="headline-md text-muted" style="margin-bottom:4px;">Upload New Paper</h3>
                <p class="body-sm text-muted" style="opacity:0.6;">PDFs are chunked, embedded and stored in Qdrant.</p>
            </div>
        </div>
    </div>`;

    document.getElementById('lib-search').addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        document.querySelectorAll('.paper-card').forEach(card => {
            card.style.display = card.textContent.toLowerCase().includes(term) ? '' : 'none';
        });
    });
    document.getElementById('lib-sort').addEventListener('change', (e) => { state.librarySort = e.target.value; renderLibrary(el); });

    // Refresh while papers are still indexing.
    if (papers.some(p => p.status === 'uploaded' || p.status === 'indexing')) {
        clearInterval(state.pollTimer);
        state.pollTimer = setInterval(async () => {
            if (state.currentPage !== 'library') return clearInterval(state.pollTimer);
            const fresh = await api.get('/papers/').catch(() => null);
            if (fresh && !fresh.some(p => p.status === 'uploaded' || p.status === 'indexing')) {
                clearInterval(state.pollTimer);
                renderLibrary(el);
            }
        }, 2500);
    }
}

function renderPaperCard(p) {
    const labels = { completed: 'Ready', indexing: 'Indexing...', uploaded: 'Queued', failed: 'Failed' };
    const ready = p.status === 'completed';
    return `
    <article class="paper-card" data-id="${p.id}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
            <span class="status-badge ${escapeHtml(p.status)}"><span class="dot"></span>${labels[p.status] || escapeHtml(p.status)}</span>
            <button class="btn-icon" style="width:32px;height:32px;border:none;" onclick="deletePaper('${p.id}')" title="Delete" aria-label="Delete paper">
                <span class="material-symbols-outlined" style="font-size:18px;">delete</span>
            </button>
        </div>
        <h3 class="paper-title">${escapeHtml(p.title)}</h3>
        <p class="paper-authors">${escapeHtml(p.authors || p.file_name)}</p>
        ${p.status === 'failed' ? `<p class="body-sm text-error" style="margin-bottom:12px;">${escapeHtml(p.error_message || 'Indexing failed.')}</p>` : ''}
        <div class="paper-meta">
            <div><span class="meta-label">Pages</span><span class="meta-value">${p.page_count || '-'}</span></div>
            <div><span class="meta-label">Chunks</span><span class="meta-value">${p.chunk_count || '-'}</span></div>
            <div><span class="meta-label">Size</span><span class="meta-value">${(p.file_size / 1048576).toFixed(1)} MB</span></div>
            <div><span class="meta-label">Added</span><span class="meta-value">${timeAgo(p.uploaded_at)}</span></div>
        </div>
        <div class="paper-actions">
            ${ready ? `
            <button class="btn-open" onclick="selectPaperAndGo('${p.id}', 'qa')"><span class="material-symbols-outlined" style="font-size:16px;">chat_bubble</span> Chat</button>
            <button class="btn-icon" title="Summarize" aria-label="Summarize" onclick="selectPaperAndGo('${p.id}', 'summary')"><span class="material-symbols-outlined">summarize</span></button>
            <button class="btn-icon" title="Study tools" aria-label="Study tools" onclick="selectPaperAndGo('${p.id}', 'study-tools')"><span class="material-symbols-outlined">quiz</span></button>`
            : p.status === 'failed' ? `
            <button class="btn-open" onclick="reindexPaper('${p.id}')"><span class="material-symbols-outlined" style="font-size:16px;">refresh</span> Retry indexing</button>`
            : '<span class="body-sm text-muted">Embedding and storing chunks...</span>'}
        </div>
    </article>`;
}

async function deletePaper(id) {
    if (!confirm('Delete this paper? Its PDF, vectors in Qdrant and cached summaries will be removed.')) return;
    if (await attempt(api.del(`/papers/${id}`))) {
        showToast('Paper deleted.', 'success');
        state.selectedPapers = state.selectedPapers.filter(p => p !== id);
        renderPage();
    }
}

async function reindexPaper(id) {
    if (await attempt(api.post(`/papers/${id}/reindex`))) {
        showToast('Re-indexing started.', 'info');
        renderPage();
    }
}

function selectPaperAndGo(id, page) {
    state.selectedPapers = [id];
    state.summaryPaper = id;
    navigate(page);
}

// ============================================================
// PAGE: Upload
// ============================================================
function renderUpload(el) {
    el.innerHTML = `
    <div style="display:flex;justify-content:center;padding-top:24px;">
        <div style="width:100%;max-width:700px;">
            <div style="text-align:center;margin-bottom:32px;">
                <h2 class="headline-lg mb-sm">Add Research Papers</h2>
                <p class="body-md text-muted">Each PDF is loaded, cleaned, split into chunks, embedded with Jina AI and stored in Qdrant.</p>
            </div>
            <div class="drop-zone" id="upload-dropzone">
                <input type="file" accept=".pdf,application/pdf" multiple id="upload-file-input" aria-label="Choose PDF files" />
                <div class="upload-icon"><span class="material-symbols-outlined" style="font-size:40px;color:var(--primary);">cloud_upload</span></div>
                <h3 class="headline-md mb-sm">Drag and drop PDFs here</h3>
                <p class="body-sm text-muted mb-md">or click to browse</p>
                <div class="file-type-badges"><div class="file-type-badge"><span class="material-symbols-outlined" style="font-size:16px;color:var(--primary);">picture_as_pdf</span> PDF, up to 50 MB</div></div>
            </div>
            <div id="upload-list" style="display:flex;flex-direction:column;gap:12px;margin-top:24px;"></div>
        </div>
    </div>`;

    const dropzone = document.getElementById('upload-dropzone');
    ['dragenter', 'dragover'].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add('drag-over'); }));
    ['dragleave', 'drop'].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove('drag-over'); }));
    dropzone.addEventListener('drop', e => [...e.dataTransfer.files].forEach(handleUpload));
    document.getElementById('upload-file-input').addEventListener('change', e => { [...e.target.files].forEach(handleUpload); e.target.value = ''; });
}

function uploadRow(rowId, name, status, detail) {
    const icons = { uploading: 'upload', uploaded: 'schedule', indexing: 'cached', completed: 'check_circle', failed: 'error' };
    const labels = { uploading: 'Uploading', uploaded: 'Queued', indexing: 'Chunking, embedding & storing', completed: 'Ready', failed: 'Failed' };
    const spin = status === 'uploading' || status === 'indexing' || status === 'uploaded';
    return `
    <div class="academic-glass upload-row" id="${rowId}">
        <span class="material-symbols-outlined ${spin ? 'processing-pulse' : ''}" style="color:${status === 'failed' ? 'var(--error)' : 'var(--primary)'};">${icons[status]}</span>
        <div style="flex:1;min-width:0;">
            <div class="label-md truncate" style="color:var(--on-surface);">${escapeHtml(name)}</div>
            <div class="label-sm ${status === 'failed' ? 'text-error' : 'text-muted'}">${escapeHtml(detail || labels[status])}</div>
        </div>
        ${status === 'completed' ? `<button class="btn-secondary" style="padding:6px 12px;" onclick="navigate('library')">Open library</button>` : ''}
    </div>`;
}

async function handleUpload(file) {
    const list = document.getElementById('upload-list');
    const rowId = `up-${Math.random().toString(36).slice(2)}`;
    list.insertAdjacentHTML('afterbegin', uploadRow(rowId, file.name, 'uploading'));
    const setRow = (status, detail) => {
        const row = document.getElementById(rowId);
        if (row) row.outerHTML = uploadRow(rowId, file.name, status, detail);
    };

    if (!file.name.toLowerCase().endsWith('.pdf')) return setRow('failed', 'Only PDF files are supported.');
    let paper;
    try { paper = await api.upload('/papers/upload', file); }
    catch (e) { return setRow('failed', e.message); }

    // Poll until the background indexing pipeline finishes.
    for (;;) {
        setRow(paper.status, paper.status === 'completed' ? `${paper.page_count} pages, ${paper.chunk_count} chunks indexed` : paper.error_message);
        if (paper.status === 'completed' || paper.status === 'failed') break;
        await new Promise(r => setTimeout(r, 1500));
        try { paper = await api.get(`/papers/${paper.id}`); } catch { break; }
    }
    if (paper.status === 'completed') showToast(`"${paper.title.substring(0, 40)}" is ready.`, 'success');
}

// ============================================================
// PAGE: QA chat (streamed)
// ============================================================
async function renderQA(el) {
    const papers = await readyPapers();
    el.innerHTML = `
    <div class="qa-layout">
        <div style="margin-bottom:var(--sp-md);">
            <label class="form-label">PAPERS TO SEARCH <span class="text-muted" style="text-transform:none;letter-spacing:0;">(none selected = whole library)</span></label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">${paperChips(papers)}</div>
        </div>
        <div class="custom-scrollbar qa-messages" id="qa-messages">
            ${state.chatHistory.length ? state.chatHistory.map(renderChatMessage).join('') : `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;opacity:0.6;text-align:center;">
                <span class="material-symbols-outlined" style="font-size:48px;color:var(--on-surface-variant);margin-bottom:16px;">chat_bubble</span>
                <p class="body-md text-muted">Answers are grounded in your papers and cite their sources.</p>
            </div>`}
        </div>
        ${state.chatHistory.length === 0 ? `
        <div class="suggested-chips" style="margin:8px 0;">
            ${['Summarize the key findings', 'Explain the methodology', 'What datasets were used?', 'What are the limitations?']
                .map(q => `<button class="suggested-chip" onclick="askSuggested(this.textContent.trim())">${q}</button>`).join('')}
        </div>` : ''}
        <div class="chat-input-box" style="position:relative;left:auto;right:auto;margin-top:8px;">
            <div class="input-inner">
                <textarea id="qa-input" rows="1" placeholder="Ask a question about your papers..." aria-label="Question"
                    oninput="this.style.height='';this.style.height=this.scrollHeight+'px'"
                    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendQuestion();}"></textarea>
                <button class="send-btn" onclick="sendQuestion()" aria-label="Send" ${state.chatBusy ? 'disabled' : ''}>
                    <span class="material-symbols-outlined" style="font-variation-settings:'wght' 700;">arrow_upward</span>
                </button>
            </div>
        </div>
        ${state.chatHistory.length ? `<div style="text-align:center;margin-top:8px;"><button class="btn-secondary" style="font-size:11px;padding:4px 12px;" onclick="clearChat()">Clear chat</button></div>` : ''}
    </div>`;
    scrollChat();
}

function scrollChat() {
    const msgs = document.getElementById('qa-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function renderChatMessage(msg, index) {
    if (msg.role === 'user') {
        return `
        <div class="chat-message" style="margin-bottom:32px;">
            <div class="chat-avatar user"><span class="material-symbols-outlined" style="color:var(--primary);font-size:20px;">person</span></div>
            <div class="chat-content"><p class="body-lg" style="color:var(--on-surface);white-space:pre-wrap;">${escapeHtml(msg.content)}</p></div>
        </div>`;
    }
    const citations = msg.citations || [];
    const score = typeof msg.score === 'number' && citations.length ? Math.round(msg.score * 100) : null;
    return `
    <div class="chat-message ai-accent-border" style="margin-bottom:32px;" id="msg-${index}">
        <div class="chat-avatar ai"><span class="material-symbols-outlined" style="color:var(--on-secondary-container);font-size:20px;">smart_toy</span></div>
        <div class="chat-content" style="display:flex;flex-direction:column;gap:16px;min-width:0;">
            ${score !== null ? `<div class="confidence-badge" title="Average cosine similarity of the retrieved chunks"><span class="dot"></span>${score}% retrieval match</div>` : ''}
            <div class="markdown body-md ${msg.error ? 'text-error' : ''}" data-answer>${msg.content ? md(msg.content) : (msg.streaming ? '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>' : '')}</div>
            ${citations.length ? `
            <details class="citations">
                <summary class="label-md text-muted">${citations.length} source${citations.length > 1 ? 's' : ''}</summary>
                <div class="citation-grid">
                    ${citations.map((c, i) => `
                    <div class="citation-card">
                        <span class="citation-tag">[${i + 1}] ${Math.round(c.score * 100)}% match</span>
                        <h4 class="label-md mb-xs" style="color:var(--on-surface);margin-top:8px;">${escapeHtml(c.paper_name)}</h4>
                        <p class="label-sm text-muted mb-sm">Page ${c.page} · ${escapeHtml(c.section || 'Unknown section')}</p>
                        <div class="citation-snippet"><p>${escapeHtml(c.text_snippet.length > 600 ? c.text_snippet.substring(0, 600) + '...' : c.text_snippet)}</p></div>
                    </div>`).join('')}
                </div>
            </details>` : ''}
        </div>
    </div>`;
}

async function sendQuestion() {
    const input = document.getElementById('qa-input');
    const question = input?.value?.trim();
    if (!question || state.chatBusy) return;

    state.chatBusy = true;
    state.chatHistory.push({ role: 'user', content: question });
    const msg = { role: 'assistant', content: '', citations: [], streaming: true };
    state.chatHistory.push(msg);
    const index = state.chatHistory.length - 1;
    renderPage();

    const refresh = (full = false) => {
        const node = document.getElementById(`msg-${index}`);
        if (!node) return;
        if (full) node.outerHTML = renderChatMessage(msg, index);
        else node.querySelector('[data-answer]').innerHTML = md(msg.content);
        scrollChat();
    };

    try {
        const res = await fetch(`${API_BASE}/qa/stream`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, paper_ids: state.selectedPapers }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => null);
            throw new Error(data?.detail || `${res.status} ${res.statusText}`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop();
            for (const raw of events) {
                if (!raw.startsWith('data: ')) continue;
                const event = JSON.parse(raw.slice(6));
                if (event.type === 'meta') { msg.citations = event.citations; msg.score = event.retrieval_score; refresh(true); }
                else if (event.type === 'token') { msg.content += event.text; refresh(); }
                else if (event.type === 'error') throw new Error(event.message);
            }
        }
    } catch (e) {
        msg.error = true;
        msg.content = (msg.content ? msg.content + '\n\n' : '') + `Error: ${e.message}`;
    }
    msg.streaming = false;
    state.chatBusy = false;
    if (state.currentPage === 'qa') refresh(true);
    document.querySelector('.send-btn')?.removeAttribute('disabled');
}

function askSuggested(q) {
    const input = document.getElementById('qa-input');
    if (input) { input.value = q; sendQuestion(); }
}

function clearChat() {
    state.chatHistory = [];
    renderPage();
}

// ============================================================
// PAGE: Summary
// ============================================================
const SUMMARY_TYPES = {
    abstract: 'Abstract', methodology: 'Methodology', results: 'Results', conclusion: 'Conclusion',
    beginner: 'Beginner friendly (ELI5)', technical: 'Technical deep-dive', bullet: 'Bullet points', 'one-page': 'One-page brief',
};

async function renderSummary(el) {
    const papers = await readyPapers();
    const selected = state.summaryPaper || state.selectedPapers[0];
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Generate Summaries</h2>
            <p class="body-md text-muted">Each summary style retrieves the most relevant chunks of the paper and summarizes only those.</p>
        </div>
        <div class="grid-2">
            <div>
                <label class="form-label" for="summary-paper">PAPER</label>
                <select class="form-select" id="summary-paper">
                    ${papers.length ? papers.map(p => `<option value="${p.id}" ${p.id === selected ? 'selected' : ''}>${escapeHtml(p.title)}</option>`).join('') : '<option disabled selected>No indexed papers</option>'}
                </select>
            </div>
            <div>
                <label class="form-label" for="summary-type">SUMMARY TYPE</label>
                <select class="form-select" id="summary-type">
                    ${Object.entries(SUMMARY_TYPES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}
                </select>
            </div>
        </div>
        <div style="display:flex;gap:12px;flex-wrap:wrap;">
            <button class="btn-primary" onclick="generateSummary(false)"><span class="material-symbols-outlined" style="font-size:18px;">auto_awesome</span> Generate Summary</button>
            <button class="btn-secondary" onclick="generateSummary(true)" title="Ignore the cached version">Regenerate</button>
        </div>
        <div id="summary-result"></div>
    </div>`;
}

async function generateSummary(refresh) {
    const paperId = document.getElementById('summary-paper')?.value;
    const summaryType = document.getElementById('summary-type')?.value;
    if (!paperId || paperId === 'No indexed papers') return showToast('Upload and index a paper first.', 'info');
    state.summaryPaper = paperId;
    const resultEl = document.getElementById('summary-result');
    resultEl.innerHTML = spinner();
    try {
        const res = await api.post('/summary', { paper_id: paperId, summary_type: summaryType, refresh });
        state.exports.summary = res.summary_text;
        resultEl.innerHTML = `
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-md);gap:12px;flex-wrap:wrap;">
                <h3 class="headline-md">${SUMMARY_TYPES[summaryType]}</h3>
                <span class="label-sm text-muted">${res.cached ? 'cached' : `${res.latency_sec.toFixed(1)}s`}</span>
            </div>
            <div class="markdown body-md">${md(res.summary_text)}</div>
            <div class="result-actions">
                <button class="btn-secondary" onclick="exportMarkdown('summary', '${summaryType}_summary.md')"><span class="material-symbols-outlined" style="font-size:16px;">download</span> Export MD</button>
            </div>
        </div>`;
    } catch (e) { resultEl.innerHTML = errorBox(e.message); }
}

// ============================================================
// PAGE: Study tools
// ============================================================
async function renderStudyTools(el) {
    const papers = await readyPapers();
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Study Tools</h2>
            <p class="body-md text-muted">Quizzes and flashcards generated from chunks spread across the whole paper.</p>
        </div>
        <div>
            <label class="form-label">SELECT PAPERS</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">${paperChips(papers)}</div>
        </div>
        <div style="display:flex;gap:8px;border-bottom:1px solid var(--outline);padding-bottom:8px;">
            <button class="chip chip-active" id="tab-quiz" onclick="showStudyTab('quiz')">Quiz</button>
            <button class="chip chip-default" id="tab-flash" onclick="showStudyTab('flash')">Flashcards</button>
        </div>
        <div id="study-quiz">
            <div class="grid-3" style="margin-bottom:var(--sp-md);">
                <div><label class="form-label" for="quiz-type">FORMAT</label><select class="form-select" id="quiz-type"><option value="mcq">Multiple choice</option><option value="true_false">True / False</option><option value="short_answer">Short answer</option></select></div>
                <div><label class="form-label" for="quiz-diff">DIFFICULTY</label><select class="form-select" id="quiz-diff"><option value="easy">Easy</option><option value="medium" selected>Medium</option><option value="hard">Hard</option></select></div>
                <div><label class="form-label" for="quiz-num">QUESTIONS</label><input type="number" class="form-input" id="quiz-num" value="5" min="1" max="15" /></div>
            </div>
            <button class="btn-primary" onclick="generateQuiz()"><span class="material-symbols-outlined" style="font-size:18px;">quiz</span> Generate Quiz</button>
            <div id="quiz-result" style="margin-top:var(--sp-lg);"></div>
        </div>
        <div id="study-flash" class="hidden">
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:var(--sp-md);flex-wrap:wrap;">
                <label class="form-label" for="flash-num" style="margin-bottom:0;">NUMBER OF CARDS</label>
                <input type="number" class="form-input" id="flash-num" value="8" min="1" max="20" style="width:80px;" />
                <button class="btn-primary" onclick="generateFlashcards()"><span class="material-symbols-outlined" style="font-size:18px;">style</span> Generate</button>
            </div>
            <div id="flash-result"></div>
        </div>
    </div>`;
    if (state.quizItems) renderQuiz(document.getElementById('quiz-result'));
    if (state.flashcards) renderFlashcard(document.getElementById('flash-result'));
}

function showStudyTab(tab) {
    document.getElementById('study-quiz').classList.toggle('hidden', tab !== 'quiz');
    document.getElementById('study-flash').classList.toggle('hidden', tab !== 'flash');
    document.getElementById('tab-quiz').className = `chip ${tab === 'quiz' ? 'chip-active' : 'chip-default'}`;
    document.getElementById('tab-flash').className = `chip ${tab === 'flash' ? 'chip-active' : 'chip-default'}`;
}

async function generateQuiz() {
    if (!state.selectedPapers.length) return showToast('Select at least one paper.', 'info');
    const resultEl = document.getElementById('quiz-result');
    resultEl.innerHTML = spinner();
    try {
        const res = await api.post('/quiz', {
            paper_ids: state.selectedPapers,
            quiz_type: document.getElementById('quiz-type').value,
            difficulty: document.getElementById('quiz-diff').value,
            num_questions: parseInt(document.getElementById('quiz-num').value, 10) || 5,
        });
        state.quizItems = res.questions;
        state.userAnswers = {};
        state.quizSubmitted = false;
        renderQuiz(resultEl);
    } catch (e) { resultEl.innerHTML = errorBox(e.message); }
}

function chooseAnswer(qi, oi) {
    if (state.quizSubmitted) return;
    state.userAnswers[qi] = state.quizItems[qi].options[oi];
    renderQuiz(document.getElementById('quiz-result'));
}

const norm = (s) => (s || '').trim().toLowerCase();

function renderQuiz(el) {
    if (!state.quizItems || !el) return;
    const done = state.quizSubmitted;
    el.innerHTML = state.quizItems.map((q, i) => `
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);margin-bottom:16px;">
            <p class="label-md mb-sm" style="color:var(--primary);">QUESTION ${i + 1}</p>
            <p class="body-md mb-md" style="color:var(--on-surface);">${escapeHtml(q.question)}</p>
            ${q.options ? q.options.map((opt, oi) => {
                const picked = state.userAnswers[i] === opt;
                const cls = done ? (norm(opt) === norm(q.answer) ? 'correct' : (picked ? 'wrong' : '')) : '';
                return `
                <button type="button" class="quiz-option ${cls} ${picked ? 'picked' : ''}" onclick="chooseAnswer(${i}, ${oi})" ${done ? 'disabled' : ''}>
                    <span class="quiz-radio"></span><span class="body-sm">${escapeHtml(opt)}</span>
                </button>`;
            }).join('') : `
                <input class="form-input" placeholder="Your answer..." value="${escapeHtml(state.userAnswers[i] || '')}" oninput="state.userAnswers[${i}]=this.value" ${done ? 'disabled' : ''} />
                ${done ? `<p class="body-sm" style="margin-top:8px;"><strong>Answer:</strong> ${escapeHtml(q.answer)}</p>` : ''}`}
            ${done && q.explanation ? `<p class="body-sm quiz-explanation"><strong>Explanation:</strong> ${escapeHtml(q.explanation)}</p>` : ''}
        </div>`).join('') + `
    <div style="display:flex;gap:12px;align-items:center;">
        ${done ? `<div class="academic-glass" style="padding:16px 24px;border-radius:var(--radius-xl);"><span class="headline-md text-primary">${quizScore()} / ${state.quizItems.length}</span><span class="label-md text-muted" style="margin-left:12px;">SCORE</span></div>
                  <button class="btn-secondary" onclick="state.quizSubmitted=false;state.userAnswers={};renderQuiz(document.getElementById('quiz-result'));">Retry</button>`
               : `<button class="btn-primary" onclick="state.quizSubmitted=true;renderQuiz(document.getElementById('quiz-result'));">Submit Answers</button>`}
    </div>`;
}

function quizScore() {
    return state.quizItems.reduce((s, q, i) => s + (norm(state.userAnswers[i]) === norm(q.answer) ? 1 : 0), 0);
}

async function generateFlashcards() {
    if (!state.selectedPapers.length) return showToast('Select at least one paper.', 'info');
    const resultEl = document.getElementById('flash-result');
    resultEl.innerHTML = spinner();
    try {
        const res = await api.post('/flashcards', {
            paper_ids: state.selectedPapers,
            num_cards: parseInt(document.getElementById('flash-num').value, 10) || 8,
        });
        state.flashcards = res.cards;
        state.cardIndex = 0;
        state.cardFlipped = false;
        renderFlashcard(resultEl);
    } catch (e) { resultEl.innerHTML = errorBox(e.message); }
}

function renderFlashcard(el) {
    if (!state.flashcards || !el) return;
    const card = state.flashcards[state.cardIndex];
    const total = state.flashcards.length;
    const idx = state.cardIndex;
    el.innerHTML = `
    <div style="display:flex;justify-content:center;gap:12px;margin-bottom:var(--sp-md);flex-wrap:wrap;">
        <button class="btn-secondary" onclick="moveCard(-1)" ${idx === 0 ? 'disabled' : ''}>Previous</button>
        <button class="btn-primary" onclick="state.cardFlipped=!state.cardFlipped;renderFlashcard(document.getElementById('flash-result'));">Flip</button>
        <button class="btn-secondary" onclick="moveCard(1)" ${idx === total - 1 ? 'disabled' : ''}>Next</button>
    </div>
    <div class="flashcard ${state.cardFlipped ? 'flipped' : ''}" onclick="state.cardFlipped=!state.cardFlipped;renderFlashcard(document.getElementById('flash-result'));" style="cursor:pointer;">
        <div class="flashcard-label">${state.cardFlipped ? 'Answer' : 'Concept'} · ${idx + 1}/${total}</div>
        <div class="flashcard-text">${escapeHtml(state.cardFlipped ? card.back : card.front)}</div>
        ${state.cardFlipped && card.explanation ? `<div class="flashcard-explanation">${escapeHtml(card.explanation)}</div>` : ''}
    </div>`;
}

function moveCard(dir) {
    state.cardIndex = Math.max(0, Math.min(state.flashcards.length - 1, state.cardIndex + dir));
    state.cardFlipped = false;
    renderFlashcard(document.getElementById('flash-result'));
}

// ============================================================
// PAGE: Research gaps
// ============================================================
async function renderResearchGaps(el) {
    const papers = await readyPapers();
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Research Gap Detector</h2>
            <p class="body-md text-muted">Retrieves limitation and future-work passages from each paper and looks for gaps and contradictions.</p>
        </div>
        <div>
            <label class="form-label">SELECT PAPERS</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">${paperChips(papers)}</div>
        </div>
        <button class="btn-primary" style="align-self:flex-start;" onclick="runGapDetection()"><span class="material-symbols-outlined" style="font-size:18px;">troubleshoot</span> Find Research Gaps</button>
        <div id="gaps-result">${state.researchGaps ? renderGaps(state.researchGaps) : ''}</div>
    </div>`;
}

async function runGapDetection() {
    if (!state.selectedPapers.length) return showToast('Select at least one paper.', 'info');
    const resultEl = document.getElementById('gaps-result');
    resultEl.innerHTML = spinner();
    try {
        const res = await api.post('/gap-detector', state.selectedPapers);
        state.researchGaps = res.gaps;
        resultEl.innerHTML = renderGaps(res.gaps);
    } catch (e) { resultEl.innerHTML = errorBox(e.message); }
}

function renderGaps(gaps) {
    if (!gaps.length) return '<p class="body-sm text-muted" style="padding:24px 0;">No research gaps found in the retrieved passages.</p>';
    const categories = { limitation: 'Limitation', missing_experiment: 'Missing experiment', contradiction: 'Contradiction', future_work: 'Future work' };
    return gaps.map(g => `
    <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;flex-wrap:wrap;">
            <h3 class="headline-md" style="flex:1;min-width:200px;">${escapeHtml(g.title)}</h3>
            <div style="display:flex;gap:8px;">
                <span class="chip chip-default">${escapeHtml(categories[g.category] || g.category)}</span>
                <span class="status-badge ${g.confidence === 'high' ? 'completed' : 'pending'}"><span class="dot"></span>${escapeHtml(g.confidence)}</span>
            </div>
        </div>
        <p class="body-md" style="color:var(--on-surface);line-height:1.7;">${escapeHtml(g.description)}</p>
        ${g.suggestion ? `<p class="body-sm quiz-explanation"><strong>Suggestion:</strong> ${escapeHtml(g.suggestion)}</p>` : ''}
        ${g.papers?.length ? `<p class="label-sm text-muted" style="margin-top:12px;">Papers: ${g.papers.map(escapeHtml).join('; ')}</p>` : ''}
    </div>`).join('');
}

// ============================================================
// PAGE: Comparison
// ============================================================
async function renderComparison(el) {
    const papers = await readyPapers();
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Paper Comparison</h2>
            <p class="body-md text-muted">A side-by-side comparison of problem, approach, datasets, results and limitations.</p>
        </div>
        <div>
            <label class="form-label">SELECT TWO OR MORE PAPERS</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">${paperChips(papers)}</div>
        </div>
        <button class="btn-primary" style="align-self:flex-start;" onclick="runComparison()"><span class="material-symbols-outlined" style="font-size:18px;">compare_arrows</span> Compare Papers</button>
        <div id="comparison-result"></div>
    </div>`;
}

async function runComparison() {
    if (state.selectedPapers.length < 2) return showToast('Select at least two papers.', 'info');
    const resultEl = document.getElementById('comparison-result');
    resultEl.innerHTML = spinner();
    try {
        const res = await api.post('/compare', state.selectedPapers);
        state.exports.comparison = res.comparison_markdown;
        resultEl.innerHTML = `
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-md);">
                <h3 class="headline-md">Comparison</h3>
                <span class="label-sm text-muted">${res.latency_sec.toFixed(1)}s</span>
            </div>
            <div class="markdown body-md">${md(res.comparison_markdown)}</div>
            <div class="result-actions">
                <button class="btn-secondary" onclick="exportMarkdown('comparison', 'comparison.md')"><span class="material-symbols-outlined" style="font-size:16px;">download</span> Export MD</button>
            </div>
        </div>`;
    } catch (e) { resultEl.innerHTML = errorBox(e.message); }
}

// ============================================================
// PAGE: Settings
// ============================================================
async function renderSettings(el) {
    const status = await attempt(api.get('/status'));
    if (!status) { el.innerHTML = errorBox('Backend unreachable.'); return; }
    const config = [
        ['LLM', `${status.llm_provider} / ${status.llm_model}`],
        ['Embedding model', `${status.embedding_model} (${status.embedding_dim}-dim)`],
        ['Qdrant collection', `${status.collection} - ${status.vectors_stored} vectors`],
        ['Similarity metric', 'Cosine'],
        ['Chunking', `Recursive, ${status.chunk_size} tokens, ${status.chunk_overlap} overlap`],
        ['Retrieval', `Semantic search, top-${status.top_k}`],
        ['Tracing', status.tracing_enabled ? 'Langfuse enabled' : 'Langfuse disabled'],
        ['Papers', status.total_papers],
    ];
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Settings</h2>
            <p class="body-md text-muted">Everything is configured in <code>.env</code>; restart the server after changes.</p>
        </div>
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <h3 class="headline-md mb-md">Services</h3>
            <div class="service-grid">${serviceRows(status.services)}</div>
        </div>
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <h3 class="headline-md mb-md">RAG configuration</h3>
            <div class="grid-2">
                ${config.map(([k, v]) => `
                <div class="config-tile">
                    <div class="label-md text-muted mb-xs">${escapeHtml(k)}</div>
                    <div class="body-sm" style="color:var(--on-surface);overflow-wrap:anywhere;">${escapeHtml(v)}</div>
                </div>`).join('')}
            </div>
        </div>
    </div>`;
}

// ============================================================
// INIT
// ============================================================
function syncFromHash() {
    state.currentPage = window.location.hash.replace('#', '') || 'dashboard';
    renderPage();
}

document.addEventListener('DOMContentLoaded', () => {
    if (window.marked) marked.setOptions({ gfm: true, breaks: true });
    window.addEventListener('hashchange', syncFromHash);
    syncFromHash();
});
