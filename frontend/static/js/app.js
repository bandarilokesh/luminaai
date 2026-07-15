/* ============================================================
   PaperMind AI — SPA Application Controller
   ============================================================ */

const API_BASE = '/api';

// ---- API Client ----
const api = {
    async get(path) {
        try {
            const r = await fetch(`${API_BASE}${path}`);
            if (!r.ok) throw new Error(`${r.status}: ${r.statusText}`);
            return await r.json();
        } catch (e) { console.error('API GET Error:', path, e); return null; }
    },
    async post(path, body) {
        try {
            const r = await fetch(`${API_BASE}${path}`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!r.ok) throw new Error(`${r.status}: ${r.statusText}`);
            return await r.json();
        } catch (e) { console.error('API POST Error:', path, e); return null; }
    },
    async upload(path, file) {
        try {
            const fd = new FormData();
            fd.append('file', file);
            const r = await fetch(`${API_BASE}${path}`, { method: 'POST', body: fd });
            if (!r.ok) throw new Error(`${r.status}: ${r.statusText}`);
            return await r.json();
        } catch (e) { console.error('API Upload Error:', path, e); return null; }
    },
    async del(path) {
        try {
            const r = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
            if (!r.ok) throw new Error(`${r.status}: ${r.statusText}`);
            return await r.json();
        } catch (e) { console.error('API DELETE Error:', path, e); return null; }
    }
};

// ---- State ----
const state = {
    currentPage: 'dashboard',
    selectedPapers: [],
    chatHistory: [],
    quizItems: null,
    userAnswers: {},
    quizSubmitted: false,
    flashcards: null,
    cardIndex: 0,
    cardFlipped: false,
    researchGaps: null
};

// ---- Toast ----
function showToast(message, type = 'info') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// ---- Time Formatting ----
function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ---- Router ----
function navigate(page) {
    state.currentPage = page;
    window.location.hash = page;
    renderPage();
    updateActiveNav();
}

function updateActiveNav() {
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === state.currentPage);
    });
    document.querySelectorAll('.mobile-nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === state.currentPage);
    });
}

function renderPage() {
    const container = document.getElementById('page-content');
    const page = state.currentPage;
    // Update topnav title
    const titles = {
        dashboard: 'Dashboard', library: 'Library', upload: 'Upload Research',
        qa: 'QA Sessions', summary: 'Summaries', 'study-tools': 'Study Tools',
        'research-gaps': 'Research Gaps', settings: 'Settings'
    };
    document.getElementById('topnav-title').textContent = titles[page] || 'PaperMind';

    container.innerHTML = '<div style="display:flex;justify-content:center;padding:80px 0;"><div class="spinner"></div></div>';

    const renderers = {
        dashboard: renderDashboard,
        library: renderLibrary,
        upload: renderUpload,
        qa: renderQA,
        summary: renderSummary,
        'study-tools': renderStudyTools,
        'research-gaps': renderResearchGaps,
        settings: renderSettings
    };

    (renderers[page] || renderDashboard)(container);
}

// ============================================================
// PAGE: Dashboard
// ============================================================
async function renderDashboard(el) {
    const [stats, activityRes, status] = await Promise.all([
        api.get('/stats'),
        api.get('/activity?limit=5'),
        api.get('/status')
    ]);

    const s = stats || { total_papers: 0, questions_asked: 0, summaries_generated: 0, study_sessions: 0 };
    const activities = activityRes?.activities || [];

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-xl);">
        <!-- Hero -->
        <section style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:var(--sp-md);">
            <div>
                <h2 class="headline-lg" style="color:var(--on-surface);margin-bottom:var(--sp-xs);">Welcome back.</h2>
                <p class="body-md text-muted">Your research command center — everything at a glance.</p>
            </div>
            <div style="display:flex;gap:var(--sp-sm);">
                <button class="btn-primary" onclick="navigate('upload')">
                    <span class="material-symbols-outlined" style="font-size:18px;">upload_file</span> Quick Upload
                </button>
                <button class="btn-secondary" onclick="navigate('qa')">
                    <span class="material-symbols-outlined" style="font-size:18px;">contact_support</span> Ask Question
                </button>
            </div>
        </section>

        <!-- Stats Grid -->
        <section class="grid-4">
            <div class="academic-glass stat-card">
                <div class="stat-icon" style="color:var(--primary-container);"><span class="material-symbols-outlined">description</span></div>
                <div class="stat-value">${s.total_papers}</div>
                <div class="stat-label">Total Papers</div>
            </div>
            <div class="academic-glass stat-card">
                <div class="stat-icon" style="color:var(--tertiary);"><span class="material-symbols-outlined">psychology</span></div>
                <div class="stat-value">${s.questions_asked}</div>
                <div class="stat-label">Questions Asked</div>
            </div>
            <div class="academic-glass stat-card">
                <div class="stat-icon" style="color:var(--secondary);"><span class="material-symbols-outlined">auto_awesome</span></div>
                <div class="stat-value">${s.summaries_generated}</div>
                <div class="stat-label">Summaries Generated</div>
            </div>
            <div class="academic-glass stat-card">
                <div class="stat-icon" style="color:var(--primary);"><span class="material-symbols-outlined">timer</span></div>
                <div class="stat-value">${s.study_sessions}</div>
                <div class="stat-label">Study Sessions</div>
            </div>
        </section>

        <!-- Main Grid -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--sp-xl);">
            <!-- Left: 2 cols -->
            <div style="grid-column: span 2;display:flex;flex-direction:column;gap:var(--sp-lg);">
                <!-- System Status -->
                <section>
                    <h3 class="headline-md mb-md" style="color:var(--on-surface);">System Status</h3>
                    <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
                        ${status ? `
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--sp-md);">
                            <div>
                                <div class="label-md text-muted" style="margin-bottom:4px;">COMPUTE</div>
                                <div class="body-sm" style="color:var(--on-surface);">
                                    ${status.gpu_available ? `<span style="color:var(--tertiary);">● CUDA Active</span>` : `<span style="color:var(--outline);">● CPU Only</span>`}
                                </div>
                                ${status.gpu_device_name ? `<div class="label-sm text-muted" style="margin-top:4px;">${escapeHtml(status.gpu_device_name)}</div>` : ''}
                            </div>
                            <div>
                                <div class="label-md text-muted" style="margin-bottom:4px;">OLLAMA</div>
                                <div class="body-sm" style="color:var(--on-surface);">
                                    ${status.ollama_running ? `<span style="color:var(--tertiary);">● Running</span>` : `<span style="color:var(--error);">● Stopped</span>`}
                                </div>
                                ${status.ollama_models?.length ? `<div class="label-sm text-muted" style="margin-top:4px;">${status.ollama_models.join(', ')}</div>` : ''}
                            </div>
                            <div>
                                <div class="label-md text-muted" style="margin-bottom:4px;">DATABASE</div>
                                <div class="body-sm" style="color:var(--on-surface);">${(status.db_size_bytes / (1024*1024)).toFixed(2)} MB</div>
                            </div>
                        </div>
                        ` : `<p class="body-sm text-error">Backend disconnected. Start the server at port 8000.</p>`}
                    </div>
                </section>

                <!-- Quick Actions -->
                <section>
                    <h3 class="headline-md mb-md" style="color:var(--on-surface);">Quick Actions</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--sp-sm);">
                        <button class="btn-secondary" style="padding:16px;flex-direction:column;gap:8px;" onclick="navigate('library')">
                            <span class="material-symbols-outlined" style="font-size:24px;color:var(--primary);">library_books</span>
                            <span class="label-md">Browse Library</span>
                        </button>
                        <button class="btn-secondary" style="padding:16px;flex-direction:column;gap:8px;" onclick="navigate('study-tools')">
                            <span class="material-symbols-outlined" style="font-size:24px;color:var(--tertiary);">school</span>
                            <span class="label-md">Study Tools</span>
                        </button>
                        <button class="btn-secondary" style="padding:16px;flex-direction:column;gap:8px;" onclick="navigate('research-gaps')">
                            <span class="material-symbols-outlined" style="font-size:24px;color:var(--secondary);">troubleshoot</span>
                            <span class="label-md">Gap Detector</span>
                        </button>
                    </div>
                </section>
            </div>

            <!-- Right: Activity Timeline -->
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-md);">
                    <h3 class="headline-md" style="color:var(--on-surface);">Recent Activity</h3>
                </div>
                ${activities.length ? `
                <div class="timeline">
                    ${activities.map(a => {
                        const icons = { upload: 'upload', qa: 'question_answer', summary: 'check_circle' };
                        const icon = icons[a.event_type] || 'bookmark';
                        return `
                        <div class="timeline-item">
                            <div class="timeline-dot ${a.event_type}">
                                <span class="material-symbols-outlined">${icon}</span>
                            </div>
                            <div>
                                <p class="label-md" style="color:var(--on-surface);">${escapeHtml(a.description)}</p>
                                <p class="label-sm text-muted">${timeAgo(a.timestamp)}</p>
                            </div>
                        </div>`;
                    }).join('')}
                </div>` : '<p class="body-sm text-muted">No activity yet. Upload a paper to get started!</p>'}
            </div>
        </div>
    </div>`;
}

// ============================================================
// PAGE: Library
// ============================================================
async function renderLibrary(el) {
    const papers = await api.get('/papers/') || [];

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <!-- Filter Bar -->
        <section style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
            <div style="display:flex;gap:8px;overflow-x:auto;">
                <span class="chip chip-active">All Papers</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px;">
                <span class="label-sm text-muted" style="text-transform:uppercase;letter-spacing:0.05em;">Sort by</span>
                <select class="form-select" id="lib-sort" style="width:auto;min-width:150px;">
                    <option value="recent">Recently Added</option>
                    <option value="title">Title</option>
                    <option value="year">Year</option>
                </select>
            </div>
        </section>

        <!-- Search -->
        <div style="position:relative;">
            <span class="material-symbols-outlined" style="position:absolute;left:16px;top:50%;transform:translateY(-50%);color:var(--on-surface-variant);font-size:18px;">search</span>
            <input class="form-input" id="lib-search" style="padding-left:44px;" placeholder="Search papers, authors, tags..." />
        </div>

        <!-- Cards Grid -->
        <div class="grid-cards" id="lib-grid">
            ${papers.map(p => renderPaperCard(p)).join('')}
            <div class="empty-state" onclick="navigate('upload')">
                <div class="empty-icon"><span class="material-symbols-outlined" style="font-size:32px;color:var(--primary);">add_notes</span></div>
                <h3 class="headline-md text-muted" style="margin-bottom:4px;">Upload New Paper</h3>
                <p class="body-sm text-muted" style="opacity:0.5;">Import PDFs to start analyzing.</p>
            </div>
        </div>
    </div>`;

    // Search filter
    document.getElementById('lib-search')?.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        document.querySelectorAll('.paper-card').forEach(card => {
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(term) ? 'flex' : 'none';
        });
    });
}

function renderPaperCard(p) {
    const statusClass = p.status || 'pending';
    const statusText = p.status === 'completed' ? 'Analyzed' : (p.status || 'Pending');
    const year = p.publication_year || 'N/A';
    const sizeMB = (p.file_size / (1024 * 1024)).toFixed(2);

    return `
    <article class="paper-card" data-id="${p.id}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
            <span class="status-badge ${statusClass}"><span class="dot"></span>${escapeHtml(statusText)}</span>
            <button class="btn-icon" style="width:32px;height:32px;border:none;" onclick="deletePaper('${p.id}')" title="Delete">
                <span class="material-symbols-outlined" style="font-size:18px;">delete</span>
            </button>
        </div>
        <h3 class="paper-title">${escapeHtml(p.title)}</h3>
        <p class="paper-authors">${escapeHtml(p.authors || 'Unknown authors')}</p>
        <div class="paper-meta">
            <div><span class="meta-label">Year</span><span class="meta-value">${year}</span></div>
            <div><span class="meta-label">Size</span><span class="meta-value">${sizeMB} MB</span></div>
        </div>
        <div class="paper-actions">
            <button class="btn-open" onclick="selectPaperAndGo('${p.id}', 'qa')"><span class="material-symbols-outlined" style="font-size:16px;">chat_bubble</span> Chat</button>
            <button class="btn-icon" title="Summarize" onclick="selectPaperAndGo('${p.id}', 'summary')"><span class="material-symbols-outlined">summarize</span></button>
            <button class="btn-icon" title="Quiz" onclick="selectPaperAndGo('${p.id}', 'study-tools')"><span class="material-symbols-outlined">quiz</span></button>
        </div>
    </article>`;
}

async function deletePaper(id) {
    if (!confirm('Delete this paper? This will remove the PDF, vectors, and all cached data.')) return;
    const res = await api.del(`/papers/${id}`);
    if (res?.success) {
        showToast('Paper deleted successfully.', 'success');
        state.selectedPapers = state.selectedPapers.filter(p => p !== id);
        renderPage();
    } else {
        showToast('Failed to delete paper.', 'error');
    }
}

function selectPaperAndGo(id, page) {
    if (!state.selectedPapers.includes(id)) state.selectedPapers.push(id);
    navigate(page);
}

// ============================================================
// PAGE: Upload
// ============================================================
function renderUpload(el) {
    el.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;">
        <div style="width:100%;max-width:700px;">
            <!-- Drop Zone -->
            <div id="upload-dropzone-section">
                <div style="text-align:center;margin-bottom:32px;">
                    <h2 class="headline-lg mb-sm">Ingest New Research</h2>
                    <p class="body-md text-muted">Our AI extracts entities, citations, and key claims instantly.</p>
                </div>
                <div class="drop-zone" id="upload-dropzone">
                    <input type="file" accept=".pdf" id="upload-file-input" />
                    <div class="upload-icon"><span class="material-symbols-outlined" style="font-size:40px;color:var(--primary);">cloud_upload</span></div>
                    <h3 class="headline-md mb-sm">Drag and drop your paper here</h3>
                    <p class="body-sm text-muted mb-md">Or click to browse from your computer</p>
                    <div class="file-type-badges">
                        <div class="file-type-badge"><span class="material-symbols-outlined" style="font-size:16px;color:var(--primary);">picture_as_pdf</span> PDF</div>
                    </div>
                    <p class="label-sm text-muted" style="margin-top:32px;opacity:0.5;">Maximum file size: 50MB</p>
                </div>
            </div>

            <!-- Processing State -->
            <div id="upload-processing" class="hidden">
                <div class="processing-card">
                    <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:32px;">
                        <div style="width:48px;height:48px;border-radius:var(--radius-lg);background:rgba(195,192,255,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <span class="material-symbols-outlined" style="color:var(--primary);">upload_file</span>
                        </div>
                        <div style="flex:1;">
                            <h3 class="headline-md mb-xs" id="upload-filename">file.pdf</h3>
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                                <span class="label-md text-primary" style="text-transform:uppercase;letter-spacing:0.1em;" id="upload-status-label">Uploading...</span>
                                <span class="label-md text-muted" id="upload-percent">0%</span>
                            </div>
                            <div class="progress-bar-bg"><div class="progress-bar-fill" id="upload-progress" style="width:0%"></div></div>
                        </div>
                    </div>
                    <div class="grid-3">
                        <div style="padding:16px;border-radius:var(--radius-lg);background:rgba(11,19,38,0.5);border:1px solid rgba(70,69,85,0.05);">
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                                <span class="label-sm text-muted">Extraction</span>
                                <span class="material-symbols-outlined processing-pulse" style="font-size:14px;color:var(--primary);">cached</span>
                            </div>
                            <p class="body-sm">Parsing entities...</p>
                        </div>
                        <div style="padding:16px;border-radius:var(--radius-lg);background:rgba(11,19,38,0.5);border:1px solid rgba(70,69,85,0.05);">
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                                <span class="label-sm text-muted">Chunking</span>
                                <span class="material-symbols-outlined" style="font-size:14px;color:rgba(199,196,216,0.3);">pending</span>
                            </div>
                            <p class="body-sm text-muted">Waiting...</p>
                        </div>
                        <div style="padding:16px;border-radius:var(--radius-lg);background:rgba(11,19,38,0.5);border:1px solid rgba(70,69,85,0.05);">
                            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                                <span class="label-sm text-muted">Indexing</span>
                                <span class="material-symbols-outlined" style="font-size:14px;color:rgba(199,196,216,0.3);">pending</span>
                            </div>
                            <p class="body-sm text-muted">Waiting...</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Success State -->
            <div id="upload-success" class="hidden">
                <div style="text-align:center;margin-bottom:32px;">
                    <div style="width:64px;height:64px;background:rgba(74,225,118,0.2);color:var(--tertiary);border-radius:var(--radius-full);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
                        <span class="material-symbols-outlined" style="font-size:32px;">check_circle</span>
                    </div>
                    <h2 class="headline-lg mb-sm">Upload Complete</h2>
                    <p class="body-md text-muted">Paper has been uploaded and indexing has started in the background.</p>
                </div>
                <div id="upload-result-meta"></div>
                <div style="display:flex;justify-content:center;gap:16px;margin-top:32px;">
                    <button class="btn-secondary" onclick="resetUpload()"><span class="material-symbols-outlined" style="font-size:18px;">add</span> Upload Another</button>
                    <button class="btn-primary" onclick="navigate('library')"><span class="material-symbols-outlined" style="font-size:18px;">library_books</span> View Library</button>
                </div>
            </div>
        </div>
    </div>`;

    // Wire up drag-and-drop
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('upload-file-input');

    ['dragenter', 'dragover'].forEach(ev => {
        dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    });
    ['dragleave', 'drop'].forEach(ev => {
        dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove('drag-over'); });
    });
    dropzone.addEventListener('drop', e => { if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]); });
    fileInput.addEventListener('change', e => { if (e.target.files.length) handleUpload(e.target.files[0]); });
}

async function handleUpload(file) {
    document.getElementById('upload-dropzone-section').classList.add('hidden');
    document.getElementById('upload-processing').classList.remove('hidden');
    document.getElementById('upload-filename').textContent = file.name;

    // Simulate progress
    const progressBar = document.getElementById('upload-progress');
    const percentLabel = document.getElementById('upload-percent');
    const statusLabel = document.getElementById('upload-status-label');
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.floor(Math.random() * 15) + 5;
        if (progress > 90) progress = 90;
        progressBar.style.width = progress + '%';
        percentLabel.textContent = progress + '%';
        if (progress > 40) statusLabel.textContent = 'Analyzing PDF...';
        if (progress > 70) statusLabel.textContent = 'Processing...';
    }, 300);

    const result = await api.upload('/papers/upload', file);
    clearInterval(interval);

    progressBar.style.width = '100%';
    percentLabel.textContent = '100%';
    statusLabel.textContent = 'Complete!';

    setTimeout(() => {
        document.getElementById('upload-processing').classList.add('hidden');
        document.getElementById('upload-success').classList.remove('hidden');

        if (result) {
            document.getElementById('upload-result-meta').innerHTML = `
            <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                    <span class="status-badge ${result.status}"><span class="dot"></span>${result.status}</span>
                    <span class="label-sm text-muted">ID: ${result.id.substring(0, 8)}...</span>
                </div>
                <h3 class="headline-md mb-sm">${escapeHtml(result.title)}</h3>
                <p class="body-sm text-muted">${escapeHtml(result.authors || 'Extracting...')}</p>
            </div>`;
        }
    }, 800);
}

function resetUpload() {
    document.getElementById('upload-success').classList.add('hidden');
    document.getElementById('upload-dropzone-section').classList.remove('hidden');
    document.getElementById('upload-progress').style.width = '0%';
    document.getElementById('upload-percent').textContent = '0%';
    document.getElementById('upload-status-label').textContent = 'Uploading...';
}

// ============================================================
// PAGE: QA Chat
// ============================================================
async function renderQA(el) {
    const papers = await api.get('/papers/') || [];
    const completedPapers = papers.filter(p => p.status === 'completed');

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;height:calc(100vh - 200px);">
        <!-- Paper selector -->
        <div style="margin-bottom:var(--sp-md);">
            <label class="form-label">SELECT PAPERS TO QUERY</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;" id="qa-paper-chips">
                ${completedPapers.length ? completedPapers.map(p => `
                    <label class="chip ${state.selectedPapers.includes(p.id) ? 'chip-active' : 'chip-default'}" style="cursor:pointer;">
                        <input type="checkbox" value="${p.id}" ${state.selectedPapers.includes(p.id) ? 'checked' : ''} style="display:none;" onchange="togglePaperSelection(this)" />
                        ${escapeHtml(p.title.substring(0, 40))}${p.title.length > 40 ? '...' : ''}
                    </label>
                `).join('') : '<p class="body-sm text-muted">No papers indexed yet. Upload papers first.</p>'}
            </div>
        </div>

        <!-- Chat Messages -->
        <div style="flex:1;overflow-y:auto;padding-bottom:180px;" class="custom-scrollbar" id="qa-messages">
            ${state.chatHistory.length === 0 ? `
                <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;opacity:0.5;">
                    <span class="material-symbols-outlined" style="font-size:48px;color:var(--outline);margin-bottom:16px;">chat_bubble</span>
                    <p class="body-md text-muted">Ask a question about your selected papers</p>
                </div>
            ` : state.chatHistory.map(msg => renderChatMessage(msg)).join('')}
        </div>

        <!-- Suggested Chips -->
        ${state.chatHistory.length === 0 ? `
        <div class="suggested-chips" style="margin-bottom:8px;">
            <button class="suggested-chip" onclick="askSuggested('Summarize key findings')"><span class="material-symbols-outlined" style="font-size:16px;">summarize</span>Summarize key findings</button>
            <button class="suggested-chip" onclick="askSuggested('Explain the methodology')"><span class="material-symbols-outlined" style="font-size:16px;">science</span>Explain methodology</button>
            <button class="suggested-chip" onclick="askSuggested('What datasets were used?')"><span class="material-symbols-outlined" style="font-size:16px;">dataset</span>What datasets?</button>
        </div>` : ''}

        <!-- Input -->
        <div style="background:linear-gradient(to top, var(--surface) 60%, transparent);padding-top:24px;">
            <div class="chat-input-box" style="position:relative;left:auto;right:auto;">
                <div class="input-inner">
                    <textarea id="qa-input" rows="1" placeholder="Ask a question about your papers..."
                        oninput="this.style.height='';this.style.height=this.scrollHeight+'px'"
                        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendQuestion();}"></textarea>
                    <button class="send-btn" onclick="sendQuestion()">
                        <span class="material-symbols-outlined" style="font-variation-settings:'wght' 700;">arrow_upward</span>
                    </button>
                </div>
            </div>
            ${state.chatHistory.length > 0 ? `<div style="text-align:center;margin-top:8px;"><button class="btn-secondary" style="font-size:11px;padding:4px 12px;" onclick="clearChat()">Clear Chat</button></div>` : ''}
        </div>
    </div>`;

    // Scroll to bottom
    const msgs = document.getElementById('qa-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function renderChatMessage(msg) {
    if (msg.role === 'user') {
        return `
        <div class="chat-message" style="margin-bottom:48px;">
            <div class="chat-avatar user"><span class="material-symbols-outlined" style="color:var(--primary);font-size:20px;">person</span></div>
            <div class="chat-content"><p class="body-lg" style="color:var(--on-surface);">${escapeHtml(msg.content)}</p></div>
        </div>`;
    }

    // AI message
    const citations = msg.citations || [];
    const conf = msg.confidence ? Math.round(msg.confidence * 100) : null;

    return `
    <div class="chat-message ai-accent-border" style="margin-bottom:48px;">
        <div class="chat-avatar ai"><span class="material-symbols-outlined" style="color:var(--on-secondary-container);font-size:20px;">smart_toy</span></div>
        <div class="chat-content" style="display:flex;flex-direction:column;gap:24px;">
            ${conf !== null ? `<div class="confidence-badge"><span class="dot"></span>${conf}% confidence</div>` : ''}
            <div class="body-md" style="color:rgba(218,226,253,0.9);line-height:1.7;white-space:pre-wrap;">${escapeHtml(msg.content)}</div>
            ${citations.length ? `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                ${citations.map((c, i) => `
                <div class="citation-card">
                    <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
                        <span class="citation-tag">Citation ${String(i + 1).padStart(2, '0')}</span>
                    </div>
                    <h4 class="label-md mb-xs" style="color:var(--on-surface);">${escapeHtml(c.paper_name)}</h4>
                    <p class="label-sm text-muted mb-sm">Page ${c.page} • Section: ${escapeHtml(c.section || 'N/A')}</p>
                    <div class="citation-snippet"><p>${escapeHtml(c.text_snippet)}</p></div>
                </div>`).join('')}
            </div>` : ''}
        </div>
    </div>`;
}

function togglePaperSelection(checkbox) {
    const id = checkbox.value;
    if (checkbox.checked) {
        if (!state.selectedPapers.includes(id)) state.selectedPapers.push(id);
    } else {
        state.selectedPapers = state.selectedPapers.filter(p => p !== id);
    }
    // Update chip style
    const label = checkbox.parentElement;
    label.className = `chip ${checkbox.checked ? 'chip-active' : 'chip-default'}`;
}

async function sendQuestion() {
    const input = document.getElementById('qa-input');
    const question = input?.value?.trim();
    if (!question || !state.selectedPapers.length) {
        if (!state.selectedPapers.length) showToast('Please select at least one paper first.', 'info');
        return;
    }

    state.chatHistory.push({ role: 'user', content: question });
    input.value = '';
    input.style.height = '';
    renderPage();

    const res = await api.post('/qa', { paper_ids: state.selectedPapers, question });
    if (res) {
        state.chatHistory.push({
            role: 'assistant', content: res.answer,
            citations: res.citations, confidence: res.confidence_score
        });
    } else {
        state.chatHistory.push({ role: 'assistant', content: 'Failed to process query. Please check the backend connection.' });
    }
    renderPage();
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
async function renderSummary(el) {
    const papers = await api.get('/papers/') || [];
    const completedPapers = papers.filter(p => p.status === 'completed');

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Generate Summaries</h2>
            <p class="body-md text-muted">Create multi-perspective summaries from your research papers.</p>
        </div>
        <div class="grid-2">
            <div>
                <label class="form-label">SELECT PAPER</label>
                <select class="form-select" id="summary-paper">
                    ${completedPapers.length ? completedPapers.map(p => `<option value="${p.id}">${escapeHtml(p.title)}</option>`).join('') : '<option disabled>No papers available</option>'}
                </select>
            </div>
            <div>
                <label class="form-label">SUMMARY TYPE</label>
                <select class="form-select" id="summary-type">
                    <option value="abstract">Abstract</option>
                    <option value="methodology">Methodology</option>
                    <option value="results">Results</option>
                    <option value="conclusion">Conclusion</option>
                    <option value="beginner">Beginner Friendly</option>
                    <option value="technical">Technical Deep-Dive</option>
                    <option value="bullet">Bullet Points</option>
                    <option value="one-page">One-Page Brief</option>
                </select>
            </div>
        </div>
        <button class="btn-primary" style="align-self:flex-start;" onclick="generateSummary()">
            <span class="material-symbols-outlined" style="font-size:18px;">auto_awesome</span> Generate Summary
        </button>
        <div id="summary-result"></div>
    </div>`;
}

async function generateSummary() {
    const paperId = document.getElementById('summary-paper')?.value;
    const summaryType = document.getElementById('summary-type')?.value;
    if (!paperId) return showToast('Select a paper first.', 'info');

    const resultEl = document.getElementById('summary-result');
    resultEl.innerHTML = '<div style="display:flex;justify-content:center;padding:40px;"><div class="spinner"></div></div>';

    const res = await api.post('/summary', { paper_id: paperId, summary_type: summaryType });
    if (res?.summary_text) {
        resultEl.innerHTML = `
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-md);">
                <h3 class="headline-md">Summary — ${escapeHtml(summaryType.replace('_', ' '))}</h3>
                <span class="label-sm text-muted">${res.latency_sec?.toFixed(1)}s</span>
            </div>
            <div class="body-md" style="line-height:1.8;white-space:pre-wrap;color:rgba(218,226,253,0.9);">${escapeHtml(res.summary_text)}</div>
            <div style="display:flex;gap:12px;margin-top:var(--sp-md);padding-top:var(--sp-md);border-top:1px solid rgba(70,69,85,0.1);">
                <button class="btn-secondary" onclick="downloadAs('${escapeHtml(summaryType)}_summary.md', \`${res.summary_text.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">
                    <span class="material-symbols-outlined" style="font-size:16px;">download</span> Export MD
                </button>
            </div>
        </div>`;
    } else {
        resultEl.innerHTML = '<p class="body-sm text-error" style="padding:24px;">Failed to generate summary.</p>';
    }
}

function downloadAs(filename, content) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

// ============================================================
// PAGE: Study Tools
// ============================================================
async function renderStudyTools(el) {
    const papers = await api.get('/papers/') || [];
    const completedPapers = papers.filter(p => p.status === 'completed');

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Study Tools</h2>
            <p class="body-md text-muted">Generate quizzes and flashcards from your research papers.</p>
        </div>

        <!-- Paper selector -->
        <div>
            <label class="form-label">SELECT PAPERS</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;" id="study-paper-chips">
                ${completedPapers.map(p => `
                    <label class="chip ${state.selectedPapers.includes(p.id) ? 'chip-active' : 'chip-default'}" style="cursor:pointer;">
                        <input type="checkbox" value="${p.id}" ${state.selectedPapers.includes(p.id) ? 'checked' : ''} style="display:none;" onchange="togglePaperSelection(this)" />
                        ${escapeHtml(p.title.substring(0, 35))}${p.title.length > 35 ? '...' : ''}
                    </label>
                `).join('') || '<p class="body-sm text-muted">No papers available.</p>'}
            </div>
        </div>

        <!-- Tabs -->
        <div style="display:flex;gap:8px;border-bottom:1px solid rgba(70,69,85,0.1);padding-bottom:8px;">
            <button class="chip chip-active" id="tab-quiz" onclick="showStudyTab('quiz')">📝 Quiz Generator</button>
            <button class="chip chip-default" id="tab-flash" onclick="showStudyTab('flash')">🗂️ Flashcards</button>
        </div>

        <!-- Quiz Tab -->
        <div id="study-quiz">
            <div class="grid-3" style="margin-bottom:var(--sp-md);">
                <div><label class="form-label">FORMAT</label><select class="form-select" id="quiz-type"><option value="mcq">Multiple Choice</option><option value="true_false">True/False</option><option value="short_answer">Short Answer</option></select></div>
                <div><label class="form-label">DIFFICULTY</label><select class="form-select" id="quiz-diff"><option value="easy">Easy</option><option value="medium" selected>Medium</option><option value="hard">Hard</option></select></div>
                <div><label class="form-label">QUESTIONS</label><input type="number" class="form-input" id="quiz-num" value="5" min="3" max="10" /></div>
            </div>
            <button class="btn-primary" onclick="generateQuiz()"><span class="material-symbols-outlined" style="font-size:18px;">quiz</span> Generate Quiz</button>
            <div id="quiz-result" style="margin-top:var(--sp-lg);"></div>
        </div>

        <!-- Flashcards Tab -->
        <div id="study-flash" class="hidden">
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:var(--sp-md);">
                <label class="form-label" style="margin-bottom:0;">NUMBER OF CARDS</label>
                <input type="number" class="form-input" id="flash-num" value="5" min="3" max="15" style="width:80px;" />
                <button class="btn-primary" onclick="generateFlashcards()"><span class="material-symbols-outlined" style="font-size:18px;">style</span> Generate</button>
            </div>
            <div id="flash-result"></div>
        </div>
    </div>`;
}

function showStudyTab(tab) {
    document.getElementById('study-quiz').classList.toggle('hidden', tab !== 'quiz');
    document.getElementById('study-flash').classList.toggle('hidden', tab !== 'flash');
    document.getElementById('tab-quiz').className = `chip ${tab === 'quiz' ? 'chip-active' : 'chip-default'}`;
    document.getElementById('tab-flash').className = `chip ${tab === 'flash' ? 'chip-active' : 'chip-default'}`;
}

async function generateQuiz() {
    if (!state.selectedPapers.length) return showToast('Select papers first.', 'info');
    const resultEl = document.getElementById('quiz-result');
    resultEl.innerHTML = '<div style="display:flex;justify-content:center;padding:40px;"><div class="spinner"></div></div>';

    const res = await api.post('/quiz', {
        paper_ids: state.selectedPapers,
        quiz_type: document.getElementById('quiz-type').value,
        difficulty: document.getElementById('quiz-diff').value,
        num_questions: parseInt(document.getElementById('quiz-num').value)
    });

    if (res?.questions) {
        state.quizItems = res.questions;
        state.userAnswers = {};
        state.quizSubmitted = false;
        renderQuiz(resultEl);
    } else {
        resultEl.innerHTML = '<p class="body-sm text-error">Failed to generate quiz.</p>';
    }
}

function renderQuiz(el) {
    if (!state.quizItems) return;
    el.innerHTML = state.quizItems.map((q, i) => `
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);margin-bottom:16px;">
            <p class="label-md mb-sm" style="color:var(--primary);">QUESTION ${i + 1}</p>
            <p class="body-md mb-md" style="color:var(--on-surface);">${escapeHtml(q.question)}</p>
            ${q.options ? q.options.map((opt, oi) => `
                <label style="display:flex;align-items:center;gap:12px;padding:8px 12px;border-radius:var(--radius-lg);cursor:pointer;transition:background 0.15s;margin-bottom:4px;${state.quizSubmitted ? (opt.toLowerCase().trim() === q.answer.toLowerCase().trim() ? 'background:rgba(74,225,118,0.1);' : (state.userAnswers[i] === opt ? 'background:rgba(255,180,171,0.1);' : '')) : ''}"
                    ${state.quizSubmitted ? '' : `onclick="state.userAnswers[${i}]='${opt.replace(/'/g, "\\'")}';renderQuiz(document.getElementById('quiz-result'));"`}>
                    <span style="width:20px;height:20px;border-radius:var(--radius-full);border:2px solid ${state.userAnswers[i] === opt ? 'var(--primary)' : 'var(--outline-variant)'};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                        ${state.userAnswers[i] === opt ? '<span style="width:10px;height:10px;border-radius:var(--radius-full);background:var(--primary);"></span>' : ''}
                    </span>
                    <span class="body-sm">${escapeHtml(opt)}</span>
                </label>
            `).join('') : `<input class="form-input" placeholder="Your answer..." value="${escapeHtml(state.userAnswers[i] || '')}" oninput="state.userAnswers[${i}]=this.value" ${state.quizSubmitted ? 'disabled' : ''} />`}
            ${state.quizSubmitted && q.explanation ? `<p class="body-sm" style="margin-top:12px;padding:12px;background:rgba(49,49,192,0.1);border-radius:var(--radius-lg);color:var(--secondary);"><strong>Explanation:</strong> ${escapeHtml(q.explanation)}</p>` : ''}
        </div>
    `).join('') + `
    <div style="display:flex;gap:12px;">
        ${!state.quizSubmitted ? `<button class="btn-primary" onclick="submitQuiz()">Submit Answers</button>` : ''}
        ${state.quizSubmitted ? `<div class="academic-glass" style="padding:16px 24px;border-radius:var(--radius-xl);"><span class="headline-md text-primary">${calculateScore()} / ${state.quizItems.length}</span><span class="label-md text-muted" style="margin-left:12px;">SCORE</span></div>` : ''}
    </div>`;
}

function submitQuiz() { state.quizSubmitted = true; renderQuiz(document.getElementById('quiz-result')); }
function calculateScore() {
    if (!state.quizItems) return 0;
    return state.quizItems.reduce((s, q, i) => {
        const u = (state.userAnswers[i] || '').trim().toLowerCase();
        return s + (u === q.answer.trim().toLowerCase() ? 1 : 0);
    }, 0);
}

async function generateFlashcards() {
    if (!state.selectedPapers.length) return showToast('Select papers first.', 'info');
    const resultEl = document.getElementById('flash-result');
    resultEl.innerHTML = '<div style="display:flex;justify-content:center;padding:40px;"><div class="spinner"></div></div>';

    const res = await api.post('/flashcards', {
        paper_ids: state.selectedPapers,
        num_cards: parseInt(document.getElementById('flash-num').value)
    });

    if (res?.cards) {
        state.flashcards = res.cards;
        state.cardIndex = 0;
        state.cardFlipped = false;
        renderFlashcard(resultEl);
    } else {
        resultEl.innerHTML = '<p class="body-sm text-error">Failed to generate flashcards.</p>';
    }
}

function renderFlashcard(el) {
    if (!state.flashcards) return;
    const card = state.flashcards[state.cardIndex];
    const total = state.flashcards.length;
    const idx = state.cardIndex;

    el.innerHTML = `
    <div style="display:flex;justify-content:center;gap:16px;margin-bottom:var(--sp-md);">
        <button class="btn-secondary" onclick="flipCard(-1)" ${idx === 0 ? 'disabled style="opacity:0.3;"' : ''}>◀ Previous</button>
        <button class="btn-primary" onclick="flipCardToggle()" style="min-width:120px;">🔄 Flip Card</button>
        <button class="btn-secondary" onclick="flipCard(1)" ${idx === total - 1 ? 'disabled style="opacity:0.3;"' : ''}>Next ▶</button>
    </div>
    <div class="flashcard ${state.cardFlipped ? 'flipped' : ''}">
        <div class="flashcard-label">${state.cardFlipped ? `Answer (Card ${idx + 1}/${total})` : `Concept (Card ${idx + 1}/${total})`}</div>
        <div class="flashcard-text">${escapeHtml(state.cardFlipped ? card.back : card.front)}</div>
        ${state.cardFlipped && card.explanation ? `<div class="flashcard-explanation">${escapeHtml(card.explanation)}</div>` : ''}
    </div>`;
}

function flipCard(dir) {
    state.cardIndex = Math.max(0, Math.min(state.flashcards.length - 1, state.cardIndex + dir));
    state.cardFlipped = false;
    renderFlashcard(document.getElementById('flash-result'));
}

function flipCardToggle() {
    state.cardFlipped = !state.cardFlipped;
    renderFlashcard(document.getElementById('flash-result'));
}

// ============================================================
// PAGE: Research Gaps
// ============================================================
async function renderResearchGaps(el) {
    const papers = await api.get('/papers/') || [];
    const completedPapers = papers.filter(p => p.status === 'completed');

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">Research Gap Detector</h2>
            <p class="body-md text-muted">Analyze papers to find contradictions, missing experiments, and unexplored areas.</p>
        </div>
        <div>
            <label class="form-label">SELECT PAPERS TO ANALYZE</label>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
                ${completedPapers.map(p => `
                    <label class="chip ${state.selectedPapers.includes(p.id) ? 'chip-active' : 'chip-default'}" style="cursor:pointer;">
                        <input type="checkbox" value="${p.id}" ${state.selectedPapers.includes(p.id) ? 'checked' : ''} style="display:none;" onchange="togglePaperSelection(this)" />
                        ${escapeHtml(p.title.substring(0, 35))}${p.title.length > 35 ? '...' : ''}
                    </label>
                `).join('') || '<p class="body-sm text-muted">No papers available.</p>'}
            </div>
        </div>
        <button class="btn-primary" style="align-self:flex-start;" onclick="runGapDetection()">
            <span class="material-symbols-outlined" style="font-size:18px;">troubleshoot</span> Run Gap Detection
        </button>
        <div id="gaps-result">${state.researchGaps ? renderGaps(state.researchGaps) : ''}</div>
    </div>`;
}

async function runGapDetection() {
    if (!state.selectedPapers.length) return showToast('Select papers first.', 'info');
    const resultEl = document.getElementById('gaps-result');
    resultEl.innerHTML = '<div style="display:flex;justify-content:center;padding:40px;"><div class="spinner"></div></div>';

    const res = await api.post('/gap-detector', state.selectedPapers);
    if (res?.gaps) {
        state.researchGaps = res.gaps;
        resultEl.innerHTML = renderGaps(res.gaps);
    } else {
        resultEl.innerHTML = '<p class="body-sm text-error">Failed to analyze gaps.</p>';
    }
}

function renderGaps(gaps) {
    if (!gaps.length) return '<p class="body-sm text-muted" style="padding:24px;">No research gaps detected.</p>';
    return gaps.map((g, i) => `
    <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span class="label-md text-primary">GAP OPPORTUNITY #${i + 1}</span>
            <span class="status-badge ${(g.confidence || 'medium') === 'high' ? 'completed' : 'pending'}">
                <span class="dot"></span>${(g.confidence || 'medium').toUpperCase()}
            </span>
        </div>
        <p class="body-sm text-muted mb-sm">Section: ${escapeHtml(g.section || 'General')}</p>
        <p class="body-md" style="color:var(--on-surface);line-height:1.7;">${escapeHtml(g.gap_description || 'No description provided.')}</p>
    </div>`).join('');
}

// ============================================================
// PAGE: Settings
// ============================================================
async function renderSettings(el) {
    const status = await api.get('/status');

    el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:var(--sp-lg);">
        <div>
            <h2 class="headline-lg mb-xs">System Settings</h2>
            <p class="body-md text-muted">Configure RAG parameters, model selection, and system preferences.</p>
        </div>

        <!-- System Status -->
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <h3 class="headline-md mb-md">System Status</h3>
            ${status ? `
            <div class="grid-4">
                <div>
                    <div class="label-md text-muted mb-xs">GPU</div>
                    <div class="body-sm">${status.gpu_available ? `<span style="color:var(--tertiary);">● Active</span>` : `<span style="color:var(--outline);">● CPU</span>`}</div>
                    ${status.gpu_device_name ? `<div class="label-sm text-muted">${escapeHtml(status.gpu_device_name)}</div>` : ''}
                </div>
                <div>
                    <div class="label-md text-muted mb-xs">OLLAMA</div>
                    <div class="body-sm">${status.ollama_running ? `<span style="color:var(--tertiary);">● Running</span>` : `<span style="color:var(--error);">● Stopped</span>`}</div>
                </div>
                <div>
                    <div class="label-md text-muted mb-xs">MODELS</div>
                    <div class="body-sm">${status.ollama_models?.join(', ') || 'None'}</div>
                </div>
                <div>
                    <div class="label-md text-muted mb-xs">DATABASE</div>
                    <div class="body-sm">${(status.db_size_bytes / (1024*1024)).toFixed(2)} MB</div>
                </div>
            </div>` : '<p class="body-sm text-error">Backend disconnected.</p>'}
        </div>

        <!-- Configuration Note -->
        <div class="academic-glass" style="padding:var(--sp-md);border-radius:var(--radius-xl);">
            <h3 class="headline-md mb-md">Configuration</h3>
            <p class="body-sm text-muted" style="line-height:1.7;">
                RAG parameters (chunk size, overlap, hybrid alpha, rerank top-N), embedding models, and LLM model selection
                are configured via the <code style="background:var(--surface-container-highest);padding:2px 6px;border-radius:4px;">config/settings.py</code> file
                or environment variables in <code style="background:var(--surface-container-highest);padding:2px 6px;border-radius:4px;">.env</code>.
            </p>
            <div class="grid-2" style="margin-top:var(--sp-md);">
                <div style="padding:16px;background:var(--surface-container-low);border-radius:var(--radius-lg);border:1px solid rgba(70,69,85,0.1);">
                    <div class="label-md text-muted mb-xs">CHUNK SIZE</div>
                    <div class="body-md">700 tokens</div>
                </div>
                <div style="padding:16px;background:var(--surface-container-low);border-radius:var(--radius-lg);border:1px solid rgba(70,69,85,0.1);">
                    <div class="label-md text-muted mb-xs">CHUNK OVERLAP</div>
                    <div class="body-md">100 tokens</div>
                </div>
                <div style="padding:16px;background:var(--surface-container-low);border-radius:var(--radius-lg);border:1px solid rgba(70,69,85,0.1);">
                    <div class="label-md text-muted mb-xs">EMBEDDING MODEL</div>
                    <div class="body-sm">BAAI/bge-small-en-v1.5</div>
                </div>
                <div style="padding:16px;background:var(--surface-container-low);border-radius:var(--radius-lg);border:1px solid rgba(70,69,85,0.1);">
                    <div class="label-md text-muted mb-xs">HYBRID ALPHA</div>
                    <div class="body-md">0.5</div>
                </div>
            </div>
        </div>
    </div>`;
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    state.currentPage = hash;
    renderPage();
    updateActiveNav();

    window.addEventListener('hashchange', () => {
        const h = window.location.hash.replace('#', '') || 'dashboard';
        state.currentPage = h;
        renderPage();
        updateActiveNav();
    });
});
